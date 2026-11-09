"""Trial tax domain: a cap on the urban IBI rate, as a forbid on the saved policy's entries (design §5.6).

The cap is 1.10 %. A policy with an `ibi_urban` entry above it is refused when the draft is saved and when it is
proposed. The figure is illustrative.
"""

from realms.legislation import F, above, forbid, pct


class Tax(above("tax")):
    ibi_urban_cap = forbid("tax_policy_propose",
        (F.code == "ibi_urban") & F.rate.is_some() & (F.rate > pct("1.10")),
        each="taxes", legislation="Trial: IBI cap (illustrative)")
