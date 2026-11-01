import React, { useEffect, useRef, useState } from "react";
import { Badge } from "../ui/Primitives.jsx";
import { money, tripDate } from "../ui/format.js";
import { displayTime, timeLabel } from "../board/time.js";

export const workspacePages = [
  ["overview", "Trip overview", "grid"],
  ["itinerary", "Itinerary canvas", "calendar"],
  ["votes", "Group decisions", "vote"],
  ["budget", "Budget & splits", "wallet"],
  ["conflicts", "Conflicts", "flag"],
  ["recommendations", "Recommendations", "spark"],
  ["concierge", "AI Concierge", "spark"],
  ["room-chat", "Room chat", "chat"],
  ["travelers", "Travelers", "people"],
  ["analytics", "Session analytics", "chart"],
  ["room-controls", "Room controls", "settings"],
  ["dataset-admin", "Dataset admin", "settings"],
];
export function Icon({ name }) {
  const paths = {
    grid: "M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z",
    calendar: "M4 5h16v16H4z M4 10h16 M8 3v4 M16 3v4",
    vote: "M5 12l4 4L19 6 M3 4v17h18",
    wallet: "M3 5h18v15H3z M15 11h6v5h-6z",
    flag: "M5 22V3h14l-3 5 3 5H5",
    spark: "m12 3 3 6 6 3-6 3-3 6-3-6-6-3 6-3z",
    chat: "M3 4h18v13H9l-6 4z",
    people:
      "M8 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8 M2 21v-3c0-5 12-5 12 0v3 M17 5a4 4 0 0 1 0 7 M18 15c4 0 4 3 4 6",
    chart: "M4 3v18h18 M9 17v-5 M14 17V8 M19 17V4",
    settings: "M4 6h16 M4 12h16 M4 18h16 M8 3v6 M16 9v6 M10 15v6",
    menu: "M4 6h16 M4 12h16 M4 18h16",
  };
  return (
    <svg
      className="workspaceIcon"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d={paths[name] || paths.grid} />
    </svg>
  );
}
export function WorkspaceSidebar({
  user,
  room,
  view,
  onNavigate,
  saveStatus,
  open,
  onClose,
}) {
  const ref = useRef(null);
  useEffect(() => {
    if (open) ref.current?.querySelector("button")?.focus();
  }, [open]);
  const pages = room
    ? [["dashboard", "Your trips", "grid"], ...workspacePages].filter(
        ([id]) =>
          (id !== "room-controls" || room.role === "leader") &&
          (id !== "dataset-admin" || user.isAdmin),
      )
    : [
        ["dashboard", "Your trips", "grid"],
        ...(user.isAdmin
          ? [["dataset-admin", "Dataset admin", "settings"]]
          : []),
      ];
  return (
    <>
      {open && (
        <button
          className="sidebarScrim"
          aria-label="Close navigation"
          onClick={onClose}
        />
      )}
      <aside
        ref={ref}
        className={"workspaceSidebar " + (open ? "isOpen" : "")}
        aria-label="Workspace navigation"
        onKeyDown={(e) => {
          if (e.key === "Escape") onClose();
        }}
      >
        <strong className="brand">
          <span>T</span>TripSync <small>AI</small>
        </strong>
        <p className="sideLabel">Workspace</p>
        <nav>
          {pages
            .filter(([id]) => !["dataset-admin", "room-controls"].includes(id))
            .map(([id, label, icon]) => (
              <button
                key={id}
                aria-current={view === id ? "page" : undefined}
                onClick={() => onNavigate(id)}
              >
                <Icon name={icon} />
                {label}
                {id === "conflicts" && <span className="navHint">Review</span>}
              </button>
            ))}
        </nav>
        {pages.some(([id]) =>
          ["dataset-admin", "room-controls"].includes(id),
        ) && (
          <>
            <p className="sideLabel">Manage</p>
            <nav>
              {pages
                .filter(([id]) =>
                  ["dataset-admin", "room-controls"].includes(id),
                )
                .map(([id, label, icon]) => (
                  <button
                    key={id}
                    aria-current={view === id ? "page" : undefined}
                    onClick={() => onNavigate(id)}
                  >
                    <Icon name={icon} />
                    {label}
                  </button>
                ))}
            </nav>
          </>
        )}
        <div className="sidebarFoot">
          <p>Private planning workspace</p>
          <strong>{room ? room.destination : "Your travel plans"}</strong>
          <p>
            {room
              ? saveStatus === "All displayed changes saved"
                ? "All changes synced"
                : saveStatus
              : "Independent educational prototype"}
          </p>
        </div>
      </aside>
    </>
  );
}
export default function TripOverview({ board, room, onNavigate }) {
  const [day, setDay] = useState(room.startDate);
  const count =
    Math.round(
      (Date.parse(room.endDate) - Date.parse(room.startDate)) / 86400000,
    ) + 1;
  const days = Array.from({ length: count }, (_, i) =>
    new Date(Date.parse(room.startDate + "T00:00:00Z") + i * 86400000)
      .toISOString()
      .slice(0, 10),
  );
  const items = board.items
    .filter((i) => displayTime(i.startTime, room).slice(0, 10) === day)
    .sort((a, b) => a.startTime.localeCompare(b.startTime));
  const openVotes = (board.votes || []).filter((v) => v.status === "open");
  const conflicts = (board.conflicts || []).filter((c) => c.status === "open");
  return (
    <section className="tripOverview" aria-label="Trip overview">
      <div className="overviewStats">
        {[
          [
            "Group budget",
            money(room.totalBudgetMinor, room.currency),
            `Across ${(board.members || room.members).length} travelers`,
          ],
          [
            "Committed so far",
            board.budgets
              ? money(board.budgets.lockedMinor, room.currency)
              : "Awaiting snapshot",
            "Locked itinerary items",
          ],
          [
            "Open decisions",
            board.roomEpoch ? openVotes.length : "—",
            "Needs group input",
          ],
          [
            "Open conflicts",
            board.roomEpoch ? conflicts.length : "—",
            "Review before locking",
          ],
        ].map(([label, value, note]) => (
          <div className="panel statCard" key={label}>
            <p>{label}</p>
            <strong>{value}</strong>
            <small>{note}</small>
          </div>
        ))}
      </div>
      <div className="overviewLayout">
        <section className="panel overviewItinerary">
          <div className="sectionTitle">
            <div>
              <h2>Shared itinerary</h2>
              <p>
                {tripDate(day)} · {timeLabel(room)}
              </p>
            </div>
            <button
              className="secondary"
              onClick={() => onNavigate("itinerary")}
            >
              Open canvas
            </button>
          </div>
          <div
            className="overviewDays"
            role="group"
            aria-label="Overview itinerary days"
          >
            {days.map((date, i) => (
              <button
                key={date}
                aria-pressed={day === date}
                onClick={() => setDay(date)}
              >
                Day {i + 1}
              </button>
            ))}
          </div>
          {!items.length && (
            <p className="emptyState">
              No activities on this day yet. Open the canvas to add your group's
              ideas.
            </p>
          )}
          {items.map((item) => (
            <article className="overviewActivity" key={item.itemId}>
              <time>
                {displayTime(item.startTime, room).slice(11)}
                <br />
                {displayTime(item.endTime, room).slice(11)}
              </time>
              <span className="activitySymbol">
                <Icon
                  name={item.lifecycleStage === "voting" ? "vote" : "calendar"}
                />
              </span>
              <div>
                <h3>{item.name}</h3>
                <small>
                  {money(item.pricePerPersonMinor, room.currency)} / person ·{" "}
                  {item.attendeeIds.length} attending
                </small>
              </div>
              <Badge tone={item.lifecycleStage}>{item.lifecycleStage}</Badge>
            </article>
          ))}
          <p className="notice">
            Use the itinerary canvas to drag activities or move them with day
            and time controls. Every update is validated by the server.
          </p>
        </section>
        <aside className="overviewContext">
          <section className="panel">
            <div className="sectionTitle">
              <h2>Budget snapshot</h2>
              <button className="link" onClick={() => onNavigate("budget")}>
                Details
              </button>
            </div>
            {board.budgets ? (
              <>
                <strong className="snapshotTotal">
                  {money(board.budgets.lockedMinor, room.currency)}
                </strong>
                <small>
                  {" "}
                  / {money(room.totalBudgetMinor, room.currency)} ceiling
                </small>
                <dl>
                  <dt>Proposed total</dt>
                  <dd>{money(board.budgets.proposedMinor, room.currency)}</dd>
                  <dt>Locked total</dt>
                  <dd>{money(board.budgets.lockedMinor, room.currency)}</dd>
                </dl>
                <p className="helpText">
                  Proposed totals include locked spending and vote reservations.
                </p>
              </>
            ) : (
              <p>Waiting for budget snapshot…</p>
            )}
          </section>
          <section className="panel">
            <div className="sectionTitle">
              <h2>Travelers</h2>
              <Badge>{(board.members || room.members).length} members</Badge>
            </div>
            {(board.members || room.members).slice(0, 5).map((m) => (
              <div className="member" key={m.userId}>
                <span className="avatar" aria-hidden="true">
                  {m.displayName.slice(0, 2).toUpperCase()}
                </span>
                <div>
                  <strong>{m.displayName}</strong>
                  <small>
                    {m.role} ·{" "}
                    {board.connectedUsers?.includes(m.userId)
                      ? "Online"
                      : "Offline"}
                  </small>
                </div>
                <i
                  className={
                    "statusDot " +
                    (board.connectedUsers?.includes(m.userId) ? "online" : "")
                  }
                  aria-hidden="true"
                />
              </div>
            ))}
            <button className="link" onClick={() => onNavigate("travelers")}>
              View all travelers
            </button>
          </section>
          <section className="panel">
            <div className="sectionTitle">
              <h2>Needs attention</h2>
              <Badge
                tone={
                  conflicts.length || openVotes.length ? "warning" : "success"
                }
              >
                {conflicts.length + openVotes.length} items
              </Badge>
            </div>
            {!conflicts.length && !openVotes.length && (
              <p>No open conflicts or votes.</p>
            )}
            {conflicts.length > 0 && (
              <div className="attentionCard">
                <h3>Schedule & budget checks</h3>
                <p>
                  {conflicts.length} open conflict
                  {conflicts.length === 1 ? "" : "s"} need review.
                </p>
                <button
                  className="secondary"
                  onClick={() => onNavigate("conflicts")}
                >
                  Review conflicts
                </button>
              </div>
            )}
            {openVotes.length > 0 && (
              <div className="attentionCard">
                <h3>Group decisions</h3>
                <p>
                  {openVotes.length} vote{openVotes.length === 1 ? "" : "s"}{" "}
                  awaiting the server deadline.
                </p>
                <button
                  className="secondary"
                  onClick={() => onNavigate("votes")}
                >
                  Review votes
                </button>
              </div>
            )}
          </section>
        </aside>
      </div>
    </section>
  );
}
