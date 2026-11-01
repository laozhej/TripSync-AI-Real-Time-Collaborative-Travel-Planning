import React, { useEffect, useState } from "react";
import SplitEditor from "./SplitEditor.jsx";
import { Badge, SectionTitle } from "../ui/Primitives.jsx";
import { money as formatMoney } from "../ui/format.js";
import { displayTime, timeLabel } from "../board/time.js";

export default function PlanningPanel({
  api,
  tripId,
  board,
  userId,
  role,
  onRefresh,
  room,
  venues = [],
  connection,
}) {
  const [error, setError] = useState(""),
    [now, setNow] = useState(Date.now()),
    [analytics, setAnalytics] = useState(null),
    [rail, setRail] = useState(null),
    [railError, setRailError] = useState(""),
    [pending, setPending] = useState(false),
    [liked, setLiked] = useState([]);
  const money = (value) =>
    formatMoney(value, board.budgets?.currency || room.currency);
  const name = (uid) =>
    board.members?.find((m) => m.userId === uid)?.displayName || "Traveler";
  const readOnly = board.trip?.status === "finalized";
  const writable =
    connection === "connected" &&
    Boolean(board.roomEpoch) &&
    !readOnly &&
    !board.trip?.roomLocked &&
    !pending;
  const canSplit =
    writable && (role === "leader" || (role === "planner" && room.canPin));
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);
  useEffect(() => {
    let active = true;
    setRailError("");
    api(`/api/v1/trips/${tripId}/recommendations`)
      .then((d) => {
        if (active) setRail(d);
      })
      .catch((e) => {
        if (active) setRailError(e.message);
      });
    return () => {
      active = false;
    };
  }, [tripId, board.roomSeq, board.recommendationsVersion]);
  async function send(path, body) {
    setError("");
    setPending(true);
    try {
      await api(`/api/v1/trips/${tripId}/${path}`, {
        method: "POST",
        body: JSON.stringify(body),
      });
      onRefresh();
      return true;
    } catch (e) {
      setError(e.message);
      onRefresh();
      return false;
    } finally {
      setPending(false);
    }
  }
  const command = () => ({
    commandId: crypto.randomUUID(),
    correlationId: crypto.randomUUID(),
  });
  const drafting = board.items.filter((i) => i.lifecycleStage === "drafting");
  const budget = board.budgets;
  const conflicts = board.conflicts || [];
  function conflictCard(c) {
    const overlap = c.data.type === "overlap";
    return (
      <article className="conflictCard" key={c.data.fingerprint}>
        <Badge
          tone={
            c.status === "resolved" ? "success" : overlap ? "warning" : "danger"
          }
        >
          {c.status}
        </Badge>
        <h3>{overlap ? "Schedule overlap" : "Budget conflict"}</h3>
        {overlap ? (
          <ul>
            {c.data.itemIds.map((id) => {
              const item = board.items.find((i) => i.itemId === id);
              return (
                <li key={id}>
                  {item ? (
                    <>
                      {item.name}
                      <br />
                      <time>
                        {displayTime(item.startTime, room)}–
                        {displayTime(item.endTime, room).slice(11)}{" "}
                        {timeLabel(room)}
                      </time>
                    </>
                  ) : (
                    "Activity no longer on the board"
                  )}
                </li>
              );
            })}
          </ul>
        ) : (
          <p>
            {c.data.details.userId ? name(c.data.details.userId) : "Group"}{" "}
            proposed: <strong>{money(c.data.details.proposedMinor)}</strong>
            <br />
            Total ceiling: <strong>{money(c.data.details.ceilingMinor)}</strong>
          </p>
        )}
        {c.status === "open" && (
          <p>
            {overlap
              ? "Move or remove a drafting activity, or resolve the contested vote."
              : "Review activities, attendee splits or the relevant total ceiling."}{" "}
            This card updates after the server confirms the change.
          </p>
        )}
      </article>
    );
  }
  return (
    <div className="planning">
      {error && <p role="alert">{error}</p>}
      <section className="panel" id="budget">
        <SectionTitle
          title="Group budget"
          description="Exact totals from your shared plan."
        />
        {budget ? (
          <>
            <div className="budgetOverview">
              <div>
                <p>Proposed spending</p>
                <strong>{money(budget.proposedMinor)}</strong>
              </div>
              <div>
                <p>Locked spending</p>
                <strong>{money(budget.lockedMinor)}</strong>
              </div>
            </div>
            <div className="tableScroll">
              <table>
                <caption className="srOnly">Per-person budget totals</caption>
                <thead>
                  <tr>
                    <th scope="col">Traveler</th>
                    <th scope="col">Proposed</th>
                    <th scope="col">Locked</th>
                  </tr>
                </thead>
                <tbody>
                  {budget.perPerson.map((p) => (
                    <tr key={p.userId}>
                      <th scope="row">
                        {name(p.userId)}
                        {p.userId === userId ? " (you)" : ""}
                      </th>
                      <td>{money(p.proposedMinor)}</td>
                      <td>{money(p.lockedMinor)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="helpText">
              Open votes reserve each traveler's highest candidate allocation.
              Category ceilings are separate from total trip ceilings.
            </p>
          </>
        ) : (
          <p role="status">Waiting for budget snapshot…</p>
        )}
        {(role === "leader" || (role === "planner" && room.canPin)) &&
          !readOnly &&
          drafting.length > 0 && (
            <>
              <h3>Edit activity splits</h3>
              <p className="helpText">
                Choose attendees and a split method. The server calculates every
                allocation.
              </p>
              {drafting.map((item) => (
                <SplitEditor
                  key={item.itemId + ":" + item.positionVersion}
                  item={item}
                  members={board.members || []}
                  disabled={!canSplit}
                  onSave={(body) =>
                    send("items/split", { ...command(), ...body })
                  }
                />
              ))}
            </>
          )}
      </section>
      <section className="panel" id="conflicts">
        <SectionTitle title="Schedule & budget conflicts">
          <Badge
            tone={
              conflicts.some((c) => c.status === "open") ? "warning" : "success"
            }
          >
            {conflicts.filter((c) => c.status === "open").length} open
          </Badge>
        </SectionTitle>
        {!conflicts.some((c) => c.status === "open") && (
          <p className="emptyState">No open conflicts.</p>
        )}
        {conflicts.filter((c) => c.status === "open").map(conflictCard)}
        {conflicts.some((c) => c.status === "resolved") && (
          <details>
            <summary>
              Resolved conflicts (
              {conflicts.filter((c) => c.status === "resolved").length})
            </summary>
            {conflicts.filter((c) => c.status === "resolved").map(conflictCard)}
          </details>
        )}
      </section>
      <section className="panel" id="votes">
        <SectionTitle
          title="Timed votes"
          description="Choose together. The server applies the result."
        />
        {!(board.votes || []).length && (
          <p className="emptyState">
            No votes yet. Candidates in an identical slot can open a vote
            automatically.
          </p>
        )}
        {(board.votes || []).map((v) => {
          const mine = v.ballots.find((b) => b.userId === userId),
            seconds = Math.max(
              0,
              Math.ceil((Date.parse(v.closesAt) - now) / 1000),
            );
          return (
            <article className="voteCard" key={v.voteId}>
              <div className="voteHeading">
                <Badge
                  tone={
                    v.status === "open"
                      ? "voting"
                      : v.status === "cancelled"
                        ? "neutral"
                        : "locked"
                  }
                >
                  {v.status === "open"
                    ? "Voting"
                    : v.status === "cancelled"
                      ? "Cancelled: no ballots"
                      : "Winner locked"}
                </Badge>
                {v.status === "open" && (
                  <strong role="timer" aria-label="Time remaining">
                    {Math.floor(seconds / 60)}:
                    {String(seconds % 60).padStart(2, "0")}
                  </strong>
                )}
              </div>
              <p className="helpText">
                Opened by {v.openedBy}.{" "}
                {v.status === "open" && seconds === 0
                  ? "Waiting for the server result."
                  : v.status === "open"
                    ? "You can change your vote until the deadline."
                    : v.status === "cancelled"
                      ? "Candidates returned to Drafting."
                      : "The winning activity is locked on the itinerary."}
              </p>
              {v.options.map((o) => {
                const item = board.items.find((i) => i.itemId === o.itemId),
                  venue = venues.find((i) => i.venueId === o.venueId),
                  selected = mine?.choiceItemId === o.itemId,
                  winner = v.winningItemId === o.itemId;
                const price = item
                  ? money(item.pricePerPersonMinor)
                  : venue
                    ? new Intl.NumberFormat("en-IN", {
                        style: "currency",
                        currency: room.currency,
                      }).format(venue.pricePerPerson)
                    : null;
                return (
                  <div
                    className="voteOption"
                    data-selected={selected}
                    data-winner={winner}
                    key={o.itemId}
                  >
                    <div className="actions">
                      <h3>{o.name}</h3>
                      {winner && <Badge tone="locked">Winner</Badge>}
                      {selected && <Badge>Your selection</Badge>}
                    </div>
                    <p>
                      {price ? `${price} / person` : "Price unavailable"}
                      <br />
                      {item
                        ? `${displayTime(item.startTime, room)}–${displayTime(item.endTime, room).slice(11)} ${timeLabel(room)}`
                        : "Historical schedule unavailable"}
                      <br />
                      {
                        v.ballots.filter((b) => b.choiceItemId === o.itemId)
                          .length
                      }{" "}
                      votes
                    </p>
                    <button
                      className="secondary"
                      disabled={
                        !writable ||
                        v.status !== "open" ||
                        seconds === 0 ||
                        !v.eligibleUserIds.includes(userId)
                      }
                      aria-pressed={selected}
                      onClick={() =>
                        send("votes/cast", {
                          ...command(),
                          voteId: v.voteId,
                          choiceVenueId: o.venueId,
                          expectedBallotVersion: mine?.version || 0,
                        })
                      }
                    >
                      Vote for {o.name}
                    </button>
                  </div>
                );
              })}
              {v.status === "open" && !v.eligibleUserIds.includes(userId) && (
                <p className="helpText">
                  You can follow this vote. Your membership is not in its
                  eligible voter list.
                </p>
              )}
            </article>
          );
        })}
        {role === "leader" && !readOnly && (
          <details>
            <summary>Open a group vote</summary>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                const form = new FormData(e.currentTarget),
                  ids = form.getAll("option");
                send("votes", {
                  ...command(),
                  expectedVersions: Object.fromEntries(
                    drafting
                      .filter((i) => ids.includes(i.itemId))
                      .map((i) => [i.itemId, i.positionVersion]),
                  ),
                  durationSeconds: Number(form.get("seconds")),
                });
              }}
            >
              <p>
                Select two or more drafting candidates sharing a time and
                attendees. Identical slots also open automatically.
              </p>
              {drafting.map((i) => (
                <label key={i.itemId}>
                  <input
                    type="checkbox"
                    name="option"
                    value={i.itemId}
                    disabled={!writable}
                  />
                  {i.name}
                </label>
              ))}
              <label>
                Vote duration (seconds)
                <input
                  name="seconds"
                  type="number"
                  min="10"
                  max="300"
                  defaultValue="60"
                  required
                  disabled={!writable}
                />
              </label>
              <button
                disabled={
                  !writable || drafting.length < 2 || !board.leaderConnected
                }
              >
                Open vote
              </button>
            </form>
          </details>
        )}
        <p className="helpText">
          Prototype rules: one changeable ballot per eligible traveler; server
          deadlines apply. Ties use stable candidate order; no turnout cancels.
        </p>
      </section>
      <section className="panel" id="recommendations">
        <SectionTitle
          title="Recommended for your group"
          description="Exploratory ideas from your group's interactions."
        />
        {railError && <p role="alert">{railError}</p>}
        {!rail && !railError && (
          <p role="status">Loading group recommendations…</p>
        )}
        {rail && (
          <>
            <Badge>
              {rail.hybridReady
                ? "Trained recommendation model"
                : "Content/popularity cold start"}
            </Badge>
            <p className="helpText">
              These ideas have not been checked for your selected slot, dietary
              requirements or ceilings. Ask Concierge to check suitability.
            </p>
            {rail.items.length === 0 && (
              <p className="emptyState">
                No more suggestions in this dataset right now.
              </p>
            )}
            {rail.items.map((i) => {
              const venue = venues.find((v) => v.venueId === i.venueId);
              return (
                <article className="recommendationCard" key={i.venueId}>
                  <Badge>{i.category}</Badge>
                  <h3>{i.name}</h3>
                  {venue && (
                    <p>
                      {new Intl.NumberFormat("en-IN", {
                        style: "currency",
                        currency: room.currency,
                      }).format(venue.pricePerPerson)}{" "}
                      / person
                      <br />
                      Dietary tags:{" "}
                      {venue.dietaryTags?.join(", ") || "None declared"}
                    </p>
                  )}
                  <p>
                    {i.reason === "content+collaborative"
                      ? "Based on activity similarity and group interaction patterns."
                      : i.reason === "content/popularity cold start"
                        ? "Based on content and popularity while interaction history is limited."
                        : i.reason}
                  </p>
                  <button
                    className="secondary"
                    disabled={readOnly || pending}
                    onClick={async () => {
                      if (
                        await send("interactions", {
                          venueId: i.venueId,
                          kind: "like",
                          eventId: crypto.randomUUID(),
                        })
                      )
                        setLiked((old) => [...new Set([...old, i.venueId])]);
                    }}
                  >
                    Like {i.name}
                  </button>
                  {liked.includes(i.venueId) && (
                    <p role="status">Like recorded.</p>
                  )}
                </article>
              );
            })}
          </>
        )}
      </section>
      <section className="panel" id="analytics">
        <h2>Session summary</h2>
        <button
          className="secondary"
          onClick={async () => {
            setError("");
            try {
              setAnalytics(await api(`/api/v1/trips/${tripId}/analytics`));
            } catch (e) {
              setError(e.message);
            }
          }}
        >
          Show session analytics
        </button>
        {analytics && (
          <>
            <p className="helpText">
              {analytics.sessionEndedAt
                ? "Finalized session"
                : "Current session · totals as of this query"}
            </p>
            <dl>
              <dt>Session duration</dt>
              <dd>
                {analytics.durationKnown
                  ? `${Math.round(analytics.sessionDurationSeconds)} seconds`
                  : "Unknown historical start"}
              </dd>
              <dt>Peak connected planners</dt>
              <dd>{analytics.peakPlanners}</dd>
              <dt>Concierge answers</dt>
              <dd>{analytics.aiCount}</dd>
              <dt>Conflicts flagged / resolved</dt>
              <dd>
                {analytics.conflictsFlagged} / {analytics.conflictsResolved}
              </dd>
              <dt>Proposed budget</dt>
              <dd>{money(analytics.finalBudgets.proposedMinor)}</dd>
              <dt>Locked budget</dt>
              <dd>{money(analytics.finalBudgets.lockedMinor)}</dd>
            </dl>
            <h3>Per-person breakdown</h3>
            {analytics.finalBudgets.perPerson.map((p) => (
              <p key={p.userId}>
                {name(p.userId)}: {money(p.proposedMinor)} proposed /{" "}
                {money(p.lockedMinor)} locked
              </p>
            ))}
          </>
        )}
        {role === "leader" && !readOnly && (
          <>
            <hr />
            <p className="helpText">
              Finalize after all activities are locked and votes and conflicts
              are resolved. The itinerary becomes read only.
            </p>
            <button
              className="primary"
              disabled={!writable || !board.leaderConnected}
              onClick={() =>
                send("finalize", {
                  ...command(),
                  expectedStateVersion: board.stateVersion,
                })
              }
            >
              Finalize trip
            </button>
          </>
        )}
      </section>
    </div>
  );
}
