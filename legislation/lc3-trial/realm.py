"""Trial realm domain: on activation every member gets one notification, so a run of the hook is countable."""

from ggg import Member
from realms.legislation import above


class Realm(above("realm")):
    def on_codex_activate(self, event):
        for member in Member.each():
            self.ggg.notification_send(recipient="User:" + member.id, topic="codex", title="Legislation active",
                                       body=event.args["codex"])
