import json
from pathlib import Path
from typing import List, Optional, Union

from httpx import ReadTimeout
from mpmath import mp

from ..sruid_utils.api.mihomo import MihomoData
from ..sruid_utils.api.mihomo.models import Avatar
from ..sruid_utils.api.mihomo.requests import get_char_card_info
from ..utils.error_reply import UID_HINT
from ..utils.excel.read_excel import AvatarPromotion, EquipmentPromotion
from ..utils.map.SR_MAP_PATH import (
    EquipmentID2Name,
    EquipmentID2Rarity,
    ItemId2Name,
    Property2Name,
    RelicId2SetId,
    SetId2Name,
    avatarId2DamageType,
    avatarId2EnName,
    avatarId2Name,
    avatarId2Rarity,
    characterSkillTree,
    rankId2Name,
    skillId2AttackType,
    skillId2Effect,
    skillId2Name,
)
from ..utils.resource.RESOURCE_PATH import PLAYER_PATH

# from gsuid_core.utils.api.minigg.request import get_weapon_info
from .cal_value import cal_relic_main_affix, cal_relic_sub_affix

mp.dps = 14


async def api_to_dict(
    sr_uid: str, sr_data: Optional[MihomoData] = None
) -> Union[List[dict], str]:
    """
    :说明:
      访问Mihomo.me API并转换为StarRailUID的数据Json。
    :参数:
      * ``uid: str``: 玩家uid。
      * ``sr_data: Optional[dict] = None``: 来自Mihomo.me的dict, 可留空。
    :返回:
      * ``刷新完成提示语: str``: 包含刷新成功的角色列表。
    """
    if '未找到绑定的UID' in sr_uid:
        return UID_HINT
    if not sr_data:
        try:
            sr_data = await get_char_card_info(sr_uid)
        except ReadTimeout:
            return '网络不太稳定...'
    if isinstance(sr_data, str):
        return []
    if isinstance(sr_data, dict):
        if 'detailInfo' not in sr_data:
            return '服务器正在维护或者关闭中...\n检查Mihomo.me是否可以访问\n如可以访问,尝试上报Bug!'
    elif sr_data is None:
        return []

    PlayerDetailInfo = sr_data['detailInfo']
    path = PLAYER_PATH / str(sr_uid)
    path.mkdir(parents=True, exist_ok=True)
    with Path.open(path / f'{sr_uid!s}.json', 'w', encoding='UTF-8') as file:
        json.dump(PlayerDetailInfo, file, ensure_ascii=False)
    with Path.open(path / 'rawData.json', 'w', encoding='UTF-8') as file:
        json.dump(sr_data, file, ensure_ascii=False)

    if 'detailInfo' not in sr_data:
        return f'SR_UID{sr_uid}刷新失败!未打开角色展柜!'

    char_name_list = []
    char_id_list = []
    im = f'UID: {sr_uid} 的角色展柜刷新成功\n'
    if PlayerDetailInfo.get('assistAvatarDetail'):
        if (
            PlayerDetailInfo['assistAvatarDetail']['avatarId']
            not in char_id_list
        ):
            char_dict, avatarName = await get_data(
                PlayerDetailInfo['assistAvatarDetail'], sr_data, sr_uid
            )
            im += f'支援角色 {avatarName}\n'
            char_name_list.append(avatarName)
            char_id_list.append(
                PlayerDetailInfo['assistAvatarDetail']['avatarId']
            )
    if PlayerDetailInfo.get('avatarDetailList'):
        im += '星海同行'
        if PlayerDetailInfo['avatarDetailList'] is not None:
            for char in PlayerDetailInfo['avatarDetailList']:
                if char['avatarId'] not in char_id_list:
                    _, avatarName = await get_data(char, sr_data, sr_uid)
                    im += f' {avatarName}'
                    char_name_list.append(avatarName)
                    char_id_list.append(char['avatarId'])

    if not char_name_list:
        return f'UID: {sr_uid} 的角色展柜刷新失败!\n请检查UID是否正确或者角色展柜是否打开!'

    return char_id_list


async def get_data(char: Avatar, sr_data: MihomoData, sr_uid: str):
    PlayerDetailInfo = sr_data['detailInfo']
    path = PLAYER_PATH / str(sr_uid)
    # 处理基本信息
    char_data = {
        'uid': str(sr_uid),
        'nickName': PlayerDetailInfo['nickname'],
        'avatarId': char['avatarId'],
        'avatarName': avatarId2Name[str(char['avatarId'])],
        'avatarElement': avatarId2DamageType[str(char['avatarId'])],
        'avatarRarity': avatarId2Rarity[str(char['avatarId'])],
        'avatarPromotion': char.get('promotion', 0),
        'avatarLevel': char['level'],
        'avatarSkill': [],
        'avatarExtraAbility': [],
        'avatarAttributeBonus': [],
        'RelicInfo': [],
    }
    avatarName = avatarId2Name[str(char['avatarId'])]
    char_data['avatarEnName'] = avatarId2EnName[str(char['avatarId'])]
    # 处理技能
    for behavior in char['skillTreeList']:
        # 处理技能
        if f'{char["avatarId"]}0' == str(behavior['pointId'])[0:5]:
            skill_temp = {}
            skill_temp['skillId'] = (
                char['avatarId'] * 100 + behavior['pointId'] % 10
            )
            skill_temp['skillName'] = skillId2Name[str(skill_temp['skillId'])]
            skill_temp['skillEffect'] = skillId2Effect[
                str(skill_temp['skillId'])
            ]
            skill_temp['skillAttackType'] = skillId2AttackType[
                str(skill_temp['skillId'])
            ]
            skill_temp['skillLevel'] = behavior['level']
            char_data['avatarSkill'].append(skill_temp)

        # 处理技能树中的额外能力
        if f'{char["avatarId"]}1' == str(behavior['pointId'])[0:5]:
            extra_ability_temp = {}
            extra_ability_temp['extraAbilityId'] = behavior['pointId']
            extra_ability_temp['extraAbilityLevel'] = behavior['level']
            char_data['avatarExtraAbility'].append(extra_ability_temp)

        # 处理技能树中的属性加成
        if f'{char["avatarId"]}2' == str(behavior['pointId'])[0:5]:
            attribute_bonus_temp = {}
            attribute_bonus_temp['attributeBonusId'] = behavior['pointId']
            attribute_bonus_temp['attributeBonusLevel'] = behavior['level']
            status_add = characterSkillTree[str(char['avatarId'])][
                str(behavior['pointId'])
            ]['levels'][behavior['level'] - 1]['properties']
            attribute_bonus_temp['statusAdd'] = {}
            if status_add:
                for property_ in status_add:
                    attribute_bonus_temp['statusAdd']['property'] = property_[
                        'type'
                    ]
                    attribute_bonus_temp['statusAdd']['name'] = Property2Name[
                        property_['type']
                    ]
                    attribute_bonus_temp['statusAdd']['value'] = property_[
                        'value'
                    ]
                    char_data['avatarAttributeBonus'].append(
                        attribute_bonus_temp
                    )

    # 处理遗器
    if char.get('relicList'):
        for relic in char['relicList']:
            relic_temp = {}
            relic_temp['relicId'] = relic['tid']
            relic_temp['relicName'] = ItemId2Name[str(relic['tid'])]
            relic_temp['SetId'] = int(RelicId2SetId[str(relic['tid'])])
            relic_temp['SetName'] = SetId2Name[str(relic_temp['SetId'])]
            relic_temp['Level'] = relic['level'] if 'level' in relic else 0
            relic_temp['Type'] = relic['type']

            relic_temp['MainAffix'] = {}
            relic_temp['MainAffix']['AffixID'] = relic['mainAffixId']
            affix_property, value = await cal_relic_main_affix(
                relic_id=relic['tid'],
                set_id=str(relic_temp['SetId']),
                affix_id=relic['mainAffixId'],
                relic_type=relic['type'],
                relic_level=relic_temp['Level'],
            )
            relic_temp['MainAffix']['Property'] = affix_property
            relic_temp['MainAffix']['Name'] = Property2Name[affix_property]
            relic_temp['MainAffix']['Value'] = value

            relic_temp['SubAffixList'] = []
            if relic.get('subAffixList'):
                for sub_affix in relic['subAffixList']:
                    sub_affix_temp = {}
                    sub_affix_temp['SubAffixID'] = sub_affix['affixId']
                    sub_affix_property, value = await cal_relic_sub_affix(
                        relic_id=relic['tid'],
                        affix_id=sub_affix['affixId'],
                        cnt=sub_affix['cnt'],
                        step=sub_affix['step'] if 'step' in sub_affix else 0,
                    )
                    sub_affix_temp['Property'] = sub_affix_property
                    sub_affix_temp['Name'] = Property2Name[sub_affix_property]
                    sub_affix_temp['Cnt'] = sub_affix['cnt']
                    sub_affix_temp['Step'] = (
                        sub_affix['step'] if 'step' in sub_affix else 0
                    )
                    sub_affix_temp['Value'] = value
                    relic_temp['SubAffixList'].append(sub_affix_temp)
            char_data['RelicInfo'].append(relic_temp)

    # 处理命座
    rank_temp = []
    if char.get('rank') and char['rank'] is not None:
        char_data['rank'] = char['rank']
        for index in range(char['rank']):
            rankTemp = {}
            rank_id = int(str(char['avatarId']) + '0' + str(index + 1))
            rankTemp['rankId'] = rank_id
            rankTemp['rankName'] = rankId2Name[str(rank_id)]
            rank_temp.append(rankTemp)
        char_data['rankList'] = rank_temp
    
    # 处理命座中的 level_up_skills
    level_up_skills = []
    if char_data.get('rankList'):
        for rank_item in char_data['rankList']:
            rank_id = rank_item['rankId']
            # 121303 -> 1213003
            behavior_id = str(rank_id)[0:5] + '0' + str(rank_id)[-1]
            char_skill_tree_data = characterSkillTree[str(char['avatarId'])].get(behavior_id, [])
            if char_skill_tree_data != [] and char_skill_tree_data['level_up_skills'] != []:
                for skill in char_skill_tree_data['level_up_skills']:
                    skill_id = skill['id']
                    skill_up_num = skill['num']
                    # 查找skill_id在不在avatarSkill中
                    for skill_item in char_data['avatarSkill']:
                        if skill_id == skill_item['skillId']:
                            skill_item['skillLevel'] += skill_up_num
                            level_up_skills.append(skill_item)
                            break


    # 处理基础属性
    base_attributes = {}
    avatar_promotion_base = AvatarPromotion[str(char['avatarId'])][
        str(char.get('promotion', 0))
    ]

    # 攻击力
    base_attributes['attack'] = str(
        mp.mpf(avatar_promotion_base["AttackBase"]['Value'])
        + mp.mpf(avatar_promotion_base["AttackAdd"]['Value'])
        * (char['level'] - 1)
    )
    # 防御力
    base_attributes['defence'] = str(
        mp.mpf(avatar_promotion_base["DefenceBase"]['Value'])
        + mp.mpf(avatar_promotion_base["DefenceAdd"]['Value'])
        * (char['level'] - 1)
    )
    # 血量
    base_attributes['hp'] = str(
        mp.mpf(avatar_promotion_base["HPBase"]['Value'])
        + mp.mpf(avatar_promotion_base["HPAdd"]['Value']) * (char['level'] - 1)
    )
    # 速度
    base_attributes['speed'] = str(
        mp.mpf(avatar_promotion_base["SpeedBase"]['Value'])
    )
    # 暴击率
    base_attributes['CriticalChanceBase'] = str(
        mp.mpf(avatar_promotion_base["CriticalChance"]['Value'])
    )
    # 暴击伤害
    base_attributes['CriticalDamageBase'] = str(
        mp.mpf(avatar_promotion_base["CriticalDamage"]['Value'])
    )
    # 嘲讽
    base_attributes['BaseAggro'] = str(
        mp.mpf(avatar_promotion_base["BaseAggro"]['Value'])
    )

    char_data['baseAttributes'] = base_attributes

    # 处理武器

    equipment_info = {}
    if char.get('equipment') and char['equipment'] is not None:
        equipment_info['equipmentID'] = char['equipment']['tid']
        equipment_info['equipmentName'] = EquipmentID2Name[
            str(char['equipment']['tid'])
        ]

        equipment_info['equipmentLevel'] = char['equipment']['level']
        equipment_info['equipmentPromotion'] = char['equipment'].get(
            'promotion', 0
        )
        equipment_info['equipmentRank'] = char['equipment']['rank']
        equipment_info['equipmentRarity'] = EquipmentID2Rarity[
            str(char['equipment']['tid'])
        ]
        equipment_base_attributes = {}
        equipment_promotion_base = EquipmentPromotion[
            str(char['equipment']['tid'])
        ][str(equipment_info['equipmentPromotion'])]

        # 生命值
        equipment_base_attributes['hp'] = str(
            mp.mpf(equipment_promotion_base["BaseHP"]['Value'])
            + mp.mpf(equipment_promotion_base["BaseHPAdd"]['Value'])
            * (char['equipment']['level'] - 1)
        )
        # 攻击力
        equipment_base_attributes['attack'] = str(
            mp.mpf(equipment_promotion_base["BaseAttack"]['Value'])
            + mp.mpf(equipment_promotion_base["BaseAttackAdd"]['Value'])
            * (char['equipment']['level'] - 1)
        )
        # 防御力
        equipment_base_attributes['defence'] = str(
            mp.mpf(equipment_promotion_base["BaseDefence"]['Value'])
            + mp.mpf(equipment_promotion_base["BaseDefenceAdd"]['Value'])
            * (char['equipment']['level'] - 1)
        )
        equipment_info['baseAttributes'] = equipment_base_attributes

    char_data['equipmentInfo'] = equipment_info

    with Path.open(path / f'{avatarName}.json', 'w', encoding='UTF-8') as file:
        json.dump(char_data, file, ensure_ascii=False)
    return char_data, avatarName


async def api_to_data(
    uid: str, mihomo_data: Optional[MihomoData] = None
) -> Union[dict, str]:
    raw_data = await api_to_dict(uid, mihomo_data)
    if isinstance(raw_data, str):
        return raw_data
    char_name_list = []
    char_name_list_str = ''
    for char_data in raw_data:
        char_name_list.append(char_data['avatarName'])
    char_name_list_str = ','.join(char_name_list)
    return f'UID{uid}刷新完成!\n本次缓存:{char_name_list_str}'
