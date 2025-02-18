import re

from gsuid_core.sv import SV
from gsuid_core.bot import Bot
from gsuid_core.models import Event
from gsuid_core.logger import logger

from ..utils.convert import get_uid
from ..utils.sr_prefix import PREFIX
from ..utils.error_reply import UID_HINT
from .draw_roleinfo_card import get_role_img, get_detail_img

sv_get_info = SV('sr查询信息')


@sv_get_info.on_command(f'{PREFIX}uid')
async def send_role_info(bot: Bot, ev: Event):
    name = ''.join(re.findall('[\u4e00-\u9fa5]', ev.text))
    if name:
        return None

    uid = await get_uid(bot, ev)
    if uid is None:
        return '你还没有绑定UID噢,请使用[sr绑定uid123]完成绑定!'

    logger.info(f'[sr查询信息]UID: {uid}')
    await bot.logger.info('开始执行[sr查询信息]')
    await bot.send(await get_role_img(uid))
    return None


@sv_get_info.on_command(f'{PREFIX}练度统计')
async def send_detail_info(bot: Bot, ev: Event):
    name = ''.join(re.findall('[\u4e00-\u9fa5]', ev.text))
    if name:
        return None
    get_uid_ = await get_uid(bot, ev, True)
    if get_uid_ is None:
        return await bot.send(UID_HINT)
    uid, user_id = get_uid_
    if uid is None:
        return await bot.send(UID_HINT)

    logger.info(f'[sr查询信息]UID: {uid}')
    await bot.logger.info('开始执行[sr查询信息]')
    await bot.send(await get_detail_img(user_id, uid))
    return None
