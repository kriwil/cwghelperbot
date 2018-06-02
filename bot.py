# -*- coding: utf-8 -*-

from datetime import time, datetime, timedelta, timezone
import json
import os

from maya import MayaDT
from telegram.ext import Updater, CommandHandler, Filters, MessageHandler, BaseFilter
import attr
import redis
import regex
import telegram

# import logging
# logging.basicConfig(
#     format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
# )
# logger = logging.getLogger(__file__)

TOKEN = os.environ.get("TELEGRAM_API_TOKEN")
CHAT_WARS_ID = 408101137
WAR_UTC_HOURS = [time(7), time(15), time(23)]

STATE_ATTACK = "⚔️"
STATE_DEFEND = "🛡"
# STATE_REST = "🛌"


_guild_info = """
🦈[1XP] aegis
Commander: FourEverClover
🏅Level: 5 🎖Glory: 3178
👥 14/15
➖
#1 🛡42 [🛡] Jagoan Neon
#2 🏹39 [⚔️] Princess
#3 🛡38 [🛡] FourEverClover
#4 🛡35 [🛌] Dragonshark
#5 🛡33 [🛌] DarkMagician
#6 🛡33 [🛡] nxyluv
#7 📦32 [🛡] And so He
#8 📦30 [🛡] GfriendSinB
#9 🛡27 [🛡] Schneeleopard
#10 ⚗️27 [🛌] Janice
#11 📦27 [🛡] xAceyx
#12 ⚒26 [🛡] to hell with
#13 📦26 [🛡] Dense
#14 📦24 [🛡] KujouMikoto
➖
More info: /g_help
"""


connection = redis.StrictRedis(host="db", port=6379, db=0)


def to_datetime(dt) -> datetime:
    if isinstance(dt, str):
        return MayaDT.from_iso8601(dt).datetime()
    return dt


@attr.s
class Guild(object):
    castle = attr.ib()
    tag = attr.ib()
    name = attr.ib()
    before_war_status = attr.ib(default=None)
    after_war_status = attr.ib(default=None)
    latest_status = attr.ib(default=None)

    @property
    def attacking(self):
        return list(filter(lambda x: x.is_attacking, self.latest_status.members))

    @property
    def defending(self):
        return list(filter(lambda x: x.is_defending, self.latest_status.members))

    @property
    def resting(self):
        return list(filter(lambda x: x.is_resting, self.latest_status.members))

    @property
    def resting_names(self):
        return [each.name for each in self.resting]

    @property
    def glory_update(self):
        if self.before_war_status and self.after_war_status:
            return self.after_war_status.glory - self.before_war_status.glory
        return 0


@attr.s
class Member(object):
    name = attr.ib()
    job = attr.ib()
    state = attr.ib()
    username = attr.ib(default="")

    @property
    def is_attacking(self):
        return self.state == STATE_ATTACK

    @property
    def is_defending(self):
        return self.state == STATE_DEFEND

    @property
    def is_resting(self):
        return not self.is_attacking and not self.is_defending


@attr.s
class Status(object):
    timestamp = attr.ib(converter=to_datetime)
    timestamp_str = attr.ib()
    glory = attr.ib(converter=int)
    members = attr.ib(default=attr.Factory(list))


class FilterGuildInfo(BaseFilter):
    def filter(self, message):
        return is_guild_info(message.text) and message.forward_from.id == CHAT_WARS_ID


def guild_info_parser(bot, update):
    message = update.message
    text = message.text
    if is_guild_info(text):
        group_id = message.chat_id
        timestamp = MayaDT.from_datetime(message.forward_date).datetime(to_timezone="UTC")
        parse_guild_info(group_id, text, timestamp=timestamp)
        # print(group_id)
        # print(message.forward_from)
        # print(message.date)
        # print(message.forward_date)
        # bot.send_message(chat_id=message.chat_id, text="ok")


def resting(bot, update):
    group_id = update.message.chat_id
    guild = get_guild(group_id)
    text = "  \n".join(guild.resting_names)
    bot.send_message(chat_id=group_id, text=text, parse_mode=telegram.ParseMode.MARKDOWN)


def glory_update(bot, update):
    group_id = update.message.chat_id
    guild = get_guild(group_id)
    text = str(guild.glory_update)
    bot.send_message(chat_id=group_id, text=text, parse_mode=telegram.ParseMode.MARKDOWN)


# def start(bot, update):
#     bot.send_message(chat_id=update.message.chat_id, text="welcome")


def unknown(bot, update):
    bot.send_message(chat_id=update.message.chat_id, text="unknown command, sorry.")


def is_guild_info(text):
    return (
        "Commander" in text and "Level" in text and "Glory" in text and "More info: /g_help" in text
    )


def parse_guild_meta(text: str) -> Guild:
    rule = r"([^\[]+)\[(\w+)\]\s+(.+)"
    match = regex.match(rule, text)
    castle = match[1]
    tag = match[2]
    name = match[3]

    return Guild(castle=castle, tag=tag, name=name)


def parse_guild_level(text: str) -> (int, int):
    rule = ".+Level:\s+(\d+).+Glory:\s+(\d+)"
    match = regex.match(rule, text)
    return match[1], match[2]


def parse_guild_member(text: str) -> Member:
    rule = r"^#(\d+)\s+([^\d]+)(\d+)\s+\[([^\]]+)\]\s+(.+)"
    match = regex.match(rule, text)
    job = match[2]
    state = match[4]
    name = match[5]

    return Member(name=name, state=state, job=job)


def get_last_war_timestamp() -> datetime:
    last_war_hour = None
    current_dt = datetime.utcnow().replace(tzinfo=timezone.utc)
    for war_hour in WAR_UTC_HOURS:
        war_dt = current_dt.replace(hour=war_hour.hour, minute=war_hour.minute)
        if war_dt < current_dt:
            last_war_hour = war_hour

    if last_war_hour is None:
        last_war_hour = WAR_UTC_HOURS[-1]
        return current_dt.replace(hour=last_war_hour.hour, minute=last_war_hour.minute) - timedelta(
            days=1
        )

    return current_dt.replace(hour=last_war_hour.hour, minute=last_war_hour.minute)


def guild_from_dict(guild_dict):
    return Guild(
        castle=guild_dict["castle"],
        tag=guild_dict["tag"],
        name=guild_dict["name"],
        before_war_status=status_from_dict(guild_dict["before_war_status"]),
        after_war_status=status_from_dict(guild_dict["after_war_status"]),
        latest_status=status_from_dict(guild_dict["latest_status"]),
    )


def status_from_dict(status_dict):
    if not status_dict:
        return None
    return Status(
        timestamp_str=status_dict["timestamp_str"],
        timestamp=status_dict["timestamp_str"],
        glory=status_dict["glory"],
        members=[member_from_dict(each) for each in status_dict["members"]],
    )


def member_from_dict(member_dict):
    return Member(
        name=member_dict["name"],
        job=member_dict["job"],
        state=member_dict["state"],
        username=member_dict["username"],
    )


def parse_guild_info(group_id, text, timestamp):
    guild = get_guild(group_id)

    text = text.strip()
    lines = text.splitlines()

    if guild is None:
        # first row: guild data
        raw_guild_data = lines[0]
        guild = parse_guild_meta(raw_guild_data)

    glory = 0
    # level = 0

    members = []
    for line in lines[1:]:
        if line.strip().startswith("🏅"):
            _, glory = parse_guild_level(line.strip())

        if line.strip().startswith("#"):
            member = parse_guild_member(line.strip())
            members.append(member)

    timestamp_str = timestamp.isoformat()
    status = Status(timestamp=timestamp, timestamp_str=timestamp_str, glory=glory, members=members)
    guild.latest_status = status

    last_war_timestamp = get_last_war_timestamp()
    if status.timestamp < last_war_timestamp:
        guild.before_war_status = status
    else:
        if guild.after_war_status is None or status.timestamp < guild.after_war_status.timestamp:
            guild.after_war_status = status

    save_guild(group_id, guild)


def save_guild(group_id, guild):
    key = f"group-{group_id}"
    guild_dict = attr.asdict(
        guild, filter=attr.filters.exclude(attr.fields(Status).timestamp, datetime)
    )
    guild_json = json.dumps(guild_dict)
    connection.execute_command("JSON.SET", key, ".", guild_json)


def get_guild(group_id):
    key = f"group-{group_id}"
    guild_dict = connection.execute_command("JSON.GET", key, "NOESCAPE")
    if guild_dict:
        return guild_from_dict(json.loads(guild_dict))
    return None


def main():
    # group_id = 111
    # parse_guild_info(group_id, _guild_info)
    # get_guild(group_id)
    # return

    filter_guild_info = FilterGuildInfo()

    updater = Updater(TOKEN)
    dispatcher = updater.dispatcher
    # dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(
        MessageHandler(Filters.forwarded & Filters.text & filter_guild_info, guild_info_parser)
    )
    dispatcher.add_handler(CommandHandler("resting", resting))
    dispatcher.add_handler(CommandHandler("glory", glory_update))
    dispatcher.add_handler(MessageHandler(Filters.command, unknown))
    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()
