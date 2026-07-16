"""
Procurement Codex
A structured process for the community to buy services and award contracts.

How it works:
  1. A member submits a procurement proposal via governance (type "procurement").
  2. If the community votes to approve it, a tender is opened for bids.
  3. Any active member (or external party) can submit a bid.
  4. When the bidding window closes, the community votes on the best bid.
  5. The winning bid becomes a contract. Payment is recorded in the budget.

This replaces ad-hoc treasury_spend proposals with a transparent bidding process.
"""

from _cdk import ic
from ggg import Proposal, Vote, User, Member, Transfer, Notification
from ic_basilisk_toolkit.date_utils import ic_time_to_epoch, epoch_to_datetime_str
import json

import budget
import governance


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BIDDING_WINDOW_DAYS = 14       # how long bidding stays open
BID_VOTE_WINDOW_DAYS = 7      # how long the community votes on bids


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso():
    return epoch_to_datetime_str(ic_time_to_epoch(ic.time())).replace(" ", "T")


def _get_tender_proposals() -> list:
    """Return all proposals that are open tenders."""
    tenders = []
    for p in Proposal.instances():
        try:
            meta = json.loads(p.metadata) if p.metadata else {}
        except (json.JSONDecodeError, TypeError):
            continue
        if meta.get("type") == "procurement_tender" and p.status == "open_for_bids":
            tenders.append(p)
    return tenders


# ---------------------------------------------------------------------------
# Open a Tender
# ---------------------------------------------------------------------------

def open_tender(user_id: str, title: str, description: str,
                budget_cap_satoshis: int) -> dict:
    """Open a new tender for bids. Only active members can create tenders.

    The tender describes what the community needs and sets a maximum budget.
    """
    if not governance._is_active_member(user_id):
        return {"opened": False, "reason": "Only active members can open tenders."}

    if budget_cap_satoshis <= 0:
        return {"opened": False, "reason": "Budget cap must be greater than zero."}

    now_epoch = ic_time_to_epoch(ic.time())
    bid_deadline = epoch_to_datetime_str(
        now_epoch + BIDDING_WINDOW_DAYS * 86400
    ).replace(" ", "T")

    metadata = json.dumps({
        "type": "procurement_tender",
        "budget_cap_satoshis": budget_cap_satoshis,
        "bids": [],
        "opened_by": user_id,
        "opened_at": _now_iso(),
    })

    user = User[user_id]
    tender = Proposal(
        title=f"Tender: {title}",
        description=description,
        status="open_for_bids",
        deadline=bid_deadline,
        proposer=user,
        metadata=metadata,
    )

    ic.print(f"Tender #{tender.id} opened by {user_id}: {title}")

    # Notify all active members
    for member in Member.instances():
        if member.identity_verification == "verified" and member.user:
            Notification(
                topic="procurement",
                title=f"New Tender: {title}",
                message=f"A new tender is open for bids. "
                        f"Budget cap: {budget_cap_satoshis} satoshis. "
                        f"Submit your bid before {bid_deadline[:10]}.",
                user=member.user,
                read=False,
                icon="shopping_cart",
                href="/extensions/voting",
                color="blue",
                metadata=f"tender_id:{tender.id}"
            )

    return {
        "opened": True,
        "tender_id": tender.id,
        "title": title,
        "budget_cap_satoshis": budget_cap_satoshis,
        "bid_deadline": bid_deadline,
    }


# ---------------------------------------------------------------------------
# Submit a Bid
# ---------------------------------------------------------------------------

def submit_bid(user_id: str, tender_id: str,
               amount_satoshis: int, description: str) -> dict:
    """Submit a bid on an open tender.

    The bid amount must not exceed the tender's budget cap.
    """
    if not governance._is_active_member(user_id):
        return {"submitted": False, "reason": "Only active members can submit bids."}

    tender = Proposal[tender_id]
    if not tender:
        return {"submitted": False, "reason": "Tender not found."}

    if tender.status != "open_for_bids":
        return {"submitted": False, "reason": "This tender is no longer accepting bids."}

    try:
        if tender.deadline and _now_iso() > tender.deadline:
            return {"submitted": False, "reason": "The bidding window has closed."}
    except (ValueError, TypeError):
        pass

    try:
        meta = json.loads(tender.metadata) if tender.metadata else {}
    except (json.JSONDecodeError, TypeError):
        meta = {}

    cap = meta.get("budget_cap_satoshis", 0)
    if amount_satoshis > cap:
        return {"submitted": False, "reason": f"Bid exceeds the budget cap of {cap} satoshis."}

    if amount_satoshis <= 0:
        return {"submitted": False, "reason": "Bid amount must be greater than zero."}

    # Check for duplicate bid from same user
    bids = meta.get("bids", [])
    for bid in bids:
        if bid["bidder"] == user_id:
            return {"submitted": False, "reason": "You have already submitted a bid on this tender."}

    # Add bid
    bid_entry = {
        "bidder": user_id,
        "amount_satoshis": amount_satoshis,
        "description": description,
        "submitted_at": _now_iso(),
    }
    bids.append(bid_entry)
    meta["bids"] = bids
    tender.metadata = json.dumps(meta)

    ic.print(f"Bid from {user_id} on tender #{tender_id}: {amount_satoshis} sat")

    return {
        "submitted": True,
        "tender_id": tender_id,
        "amount_satoshis": amount_satoshis,
        "bid_number": len(bids),
    }


# ---------------------------------------------------------------------------
# Close Bidding and Open Vote
# ---------------------------------------------------------------------------

def close_bidding() -> dict:
    """Close tenders whose bidding window has passed and open voting.

    Designed to run as part of a scheduled task.
    """
    now_str = _now_iso()
    closed = 0

    for tender in Proposal.instances():
        if tender.status != "open_for_bids":
            continue

        try:
            meta = json.loads(tender.metadata) if tender.metadata else {}
        except (json.JSONDecodeError, TypeError):
            continue

        if meta.get("type") != "procurement_tender":
            continue

        try:
            if tender.deadline and tender.deadline > now_str:
                continue
        except (ValueError, TypeError):
            continue

        bids = meta.get("bids", [])
        if not bids:
            tender.status = "no_bids"
            ic.print(f"Tender #{tender.id} closed with no bids")
            closed += 1
            continue

        # Move to voting phase — community votes yes/no on the cheapest bid
        bids.sort(key=lambda b: b["amount_satoshis"])
        meta["winning_bid_candidate"] = bids[0]
        tender.metadata = json.dumps(meta)

        now_epoch = ic_time_to_epoch(ic.time())
        vote_deadline = epoch_to_datetime_str(
            now_epoch + BID_VOTE_WINDOW_DAYS * 86400
        ).replace(" ", "T")
        tender.deadline = vote_deadline
        tender.status = "voting"
        closed += 1

        best = bids[0]
        ic.print(f"Tender #{tender.id} bidding closed. "
                 f"Best bid: {best['amount_satoshis']} sat by {best['bidder']}. "
                 f"Community vote until {vote_deadline[:10]}.")

        # Notify members about the vote
        for member in Member.instances():
            if member.identity_verification == "verified" and member.user:
                Notification(
                    topic="procurement",
                    title=f"Vote on Tender: {tender.title}",
                    message=f"Bidding closed. Best bid: {best['amount_satoshis']} sat "
                            f"by {best['bidder']}. Vote to approve or reject.",
                    user=member.user,
                    read=False,
                    icon="shopping_cart",
                    href="/extensions/voting",
                    color="blue",
                    metadata=f"tender_id:{tender.id}"
                )

    return {"closed": closed}


# ---------------------------------------------------------------------------
# Award Contract (after governance vote passes)
# ---------------------------------------------------------------------------

def award_contract(tender_id: str) -> dict:
    """Award the contract to the winning bidder and record the payment.

    Called when a procurement tender's governance vote passes.
    """
    tender = Proposal[tender_id]
    if not tender:
        return {"awarded": False, "reason": "Tender not found."}

    try:
        meta = json.loads(tender.metadata) if tender.metadata else {}
    except (json.JSONDecodeError, TypeError):
        return {"awarded": False, "reason": "Invalid tender metadata."}

    best = meta.get("winning_bid_candidate")
    if not best:
        return {"awarded": False, "reason": "No winning bid found."}

    bidder = best["bidder"]
    amount_sat = best["amount_satoshis"]
    amount_btc = amount_sat / budget.SATOSHIS_PER_BTC

    # Record payment in the budget
    budget.record_service_payment(
        recipient=bidder,
        amount_btc=amount_btc,
        currency="ckBTC",
        description=f"Procurement contract — tender #{tender_id}"
    )

    # Create transfer record
    Transfer(
        amount=amount_btc,
        currency="ckBTC",
        to_principal=bidder,
        status="Completed",
        metadata=json.dumps({
            "type": "procurement",
            "tender_id": tender_id,
            "awarded_at": _now_iso(),
        })
    )

    tender.status = "awarded"
    ic.print(f"Tender #{tender_id} awarded to {bidder} for {amount_sat} sat")

    # Notify the winner
    winner_user = User[bidder]
    if winner_user:
        Notification(
            topic="procurement",
            title=f"Contract Awarded: {tender.title}",
            message=f"Your bid of {amount_sat} satoshis has been accepted. "
                    f"Payment has been recorded.",
            user=winner_user,
            read=False,
            icon="shopping_cart",
            href="/extensions/voting",
            color="green",
            metadata=f"tender_id:{tender_id}"
        )

    return {
        "awarded": True,
        "tender_id": tender_id,
        "winner": bidder,
        "amount_satoshis": amount_sat,
    }


# ---------------------------------------------------------------------------
# Scheduled Task Entry Point
# ---------------------------------------------------------------------------

def async_task():
    """Entry point for the Task Manager scheduled execution."""
    return close_bidding()


# ---------------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------------

def get_tender_summary(tender_id: str) -> dict:
    """Get details about a tender including all bids."""
    tender = Proposal[tender_id]
    if not tender:
        return {"error": "Tender not found"}

    try:
        meta = json.loads(tender.metadata) if tender.metadata else {}
    except (json.JSONDecodeError, TypeError):
        meta = {}

    return {
        "tender_id": tender.id,
        "title": tender.title,
        "status": tender.status,
        "deadline": tender.deadline,
        "budget_cap_satoshis": meta.get("budget_cap_satoshis"),
        "bids": meta.get("bids", []),
        "winning_bid": meta.get("winning_bid_candidate"),
    }


def list_open_tenders() -> list:
    """List all tenders currently open for bids."""
    results = []
    for tender in _get_tender_proposals():
        try:
            meta = json.loads(tender.metadata) if tender.metadata else {}
        except (json.JSONDecodeError, TypeError):
            meta = {}
        results.append({
            "tender_id": tender.id,
            "title": tender.title,
            "deadline": tender.deadline,
            "budget_cap_satoshis": meta.get("budget_cap_satoshis"),
            "bid_count": len(meta.get("bids", [])),
        })
    return results


if __name__ == "__main__":
    print(json.dumps(list_open_tenders(), indent=2))
