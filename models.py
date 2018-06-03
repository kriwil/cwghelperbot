from datetime import datetime

from maya import MayaDT
import attr

STATE_ATTACK = "⚔"
STATE_DEFEND = "🛡"
# STATE_REST = "🛌"


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
