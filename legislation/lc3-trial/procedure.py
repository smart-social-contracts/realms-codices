"""Trial procedure domain: two probes for the runtime, triggered only by a proposal title that names them.

A proposal titled RAISE-GUARD is refused by a guard that raises; one titled RAISE-HOOK passes, and the hook that runs
after it raises (the failure is counted in codex_status and never reaches the proposal).
"""

from realms.legislation import above


class Procedure(above("procedure")):
    def check_proposal_create(self, args):
        if "RAISE-GUARD" in args.title:
            raise ValueError("trial guard raises")
        return None

    def on_proposal_create(self, event):
        if "RAISE-HOOK" in event.args["title"]:
            raise ValueError("trial hook raises")
