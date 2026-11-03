# Watch a shared activity in two browsers

This first collaboration check uses two demo accounts and one local TripSync instance. It covers room creation, joining and a shared pin (PRD §§5.1,6.1; REQ-004/005/008), without requiring an AI request.

## Before you start

Complete [environment setup](ENVIRONMENT_SETUP.md): migrate the database, import the authored Bengaluru dataset, and keep the API running with **one worker** plus the Vite client. Open the same Vite address in two separate browser profiles (A and B), or two different browsers; ordinary tabs in one profile share a login. Use two different demo accounts: choose **Create account** if needed, then sign in separately. Keep invitations private.

## Create, join and add an activity

1. **In A, create a room.** Under **Start a trip**, keep Bengaluru, select a start and end date, leave a suitable group budget such as ₹25,000, and choose **Create room**. This account is the Leader. Open **Itinerary canvas** and wait for **Live connection**.
2. **In A, invite the second account.** Choose **Invite travelers**, then under **Invite controls** select **Planner** as the **Participant role** and choose **Create invitation**. Copy the displayed code from **Invite your group**. This explicit invitation is single-use; create a new one if it expires or has already been redeemed.
3. **In B, join the same room.** Under **Join a trip**, paste that code into **Invitation code** and choose **Join room**. Open **Itinerary canvas**. Check that both sessions show the same destination and trip dates and both say **Live connection**. The Leader and Planner are distinct trip members; see the [permission matrix](PROJECT_REQUIREMENTS.md#roles-and-journeys).
4. **In A, pin one sample activity.** Under **Ideas for your trip**, set **Day** to a date inside the trip and **Start time (IST)** to **12:00**. Find **Synthetic City Museum** and choose its **Add to itinerary** button once. The new pin lasts one hour; the catalog and its ₹200/person price are fictional demonstration data.
5. **Watch B without refreshing.** The same museum activity should appear in **Shared itinerary** in both sessions at 12:00–13:00 IST on the selected day. Select that day in each board if necessary. Wait until both status bars say **All displayed changes saved**; **Saving changes…** is not yet a durable-save confirmation.

The check succeeds when one pin appears in both sessions, with the same venue, day and time, without reloading B. This is a functional check, not a latency measurement. For moves, reconnects, votes and the full evidence sequence, continue with [the demo guide](DEMO_AND_SUBMISSION.md#repeatable-demonstration).

## If the activity does not appear

- **No live connection:** keep both servers running, confirm both profiles use the same frontend address, and check the configured allowed origin in the setup guide. Wait for reconnect and its room snapshot before editing.
- **Join rejected:** have the Leader create a fresh Planner invitation; use an active, unlocked room and an account that has not been removed from it.
- **Add button disabled:** confirm the account is Leader or Planner with editing allowed, and the trip is neither locked nor finalized. A Viewer cannot pin activities.
- **Different view or day:** open **Itinerary canvas** in both sessions and select the pin's day. Check that B joined A's room instead of creating a second one.
- **Saving unavailable:** record the displayed error and investigate API/database readiness using the setup guide; do not count the pin as saved.
