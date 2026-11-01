import React, { useEffect, useRef, useState } from "react";
import { Badge } from "../ui/Primitives.jsx";
import { money, tripDate } from "../ui/format.js";
import {
  planningRange as utcDateRange,
  displayTime,
  timeLabel,
} from "./time.js";

export default function BoardGrid({
  board,
  room,
  connection,
  onSelectedMove,
  onDropMove,
  onRemove,
  onLock,
  onUnlock,
}) {
  const [offset, O] = useState(0);
  const [selected, select] = useState(null);
  const scroll = useRef(null);
  const range = utcDateRange(room);
  const first = Date.parse(range.startDate + "T00:00:00Z"),
    count = range.count;
  const start = Math.min(offset, Math.max(0, count - 1));
  const days = Array.from({ length: Math.min(7, count - start) }, (_, i) => ({
    index: start + i,
    date: new Date(first + (start + i) * 86400000).toISOString().slice(0, 10),
  }));
  const visibleDays =
    selected === null ? days : days.filter((day) => day.date === selected);
  // Keep the full 24-hour canvas, but open around actual activities rather than midnight.
  useEffect(() => {
    const hours = board.items
      .filter((item) =>
        visibleDays.some(
          (day) => day.date === displayTime(item.startTime, room).slice(0, 10),
        ),
      )
      .map((item) => Number(displayTime(item.startTime, room).slice(11, 13)));
    const hour = hours.length ? Math.min(...hours) : 9;
    const row = scroll.current?.querySelector(
      `[data-hour="${Math.max(0, hour - 1)}"]`,
    );
    if (row && scroll.current)
      scroll.current.scrollTop = Math.max(0, row.offsetTop - 80);
  }, [selected, start, board.items.length]);
  const canEdit =
    connection === "connected" &&
    board.trip?.status !== "finalized" &&
    !board.trip?.roomLocked &&
    (room.role === "leader" || (room.role === "planner" && room.canPin));
  const canLead =
    connection === "connected" &&
    board.trip?.status !== "finalized" &&
    !board.trip?.roomLocked &&
    room.role === "leader" &&
    board.leaderConnected;
  function drop(event, day, hour) {
    event.preventDefault();
    if (!canEdit) return;
    let drag, current;
    try {
      const text = event.dataTransfer.getData("application/tripsync-item");
      if (text.length > 2048) return;
      drag = JSON.parse(text);
      current = board.items.find((item) => item.itemId === drag.itemId);
      if (
        !current ||
        !Number.isSafeInteger(drag.positionVersion) ||
        drag.positionVersion < 1
      )
        return;
    } catch {
      return;
    }
    onDropMove(
      { ...current, positionVersion: drag.positionVersion },
      day.date,
      hour,
    );
  }
  return (
    <div className="dayGrid">
      <div className="gridNav">
        <button
          className="link"
          disabled={start === 0}
          onClick={() => {
            select(null);
            O(Math.max(0, start - 7));
          }}
        >
          Previous days
        </button>
        <span>
          Days {start + 1}–{start + days.length} of {count}
        </span>
        <button
          className="link"
          disabled={start + days.length >= count}
          onClick={() => {
            select(null);
            O(start + 7);
          }}
        >
          Next days
        </button>
      </div>
      <div className="dayTabs" role="group" aria-label="Choose itinerary day">
        <button
          className="secondary"
          aria-pressed={selected === null}
          onClick={() => select(null)}
        >
          All days<small>Week view</small>
        </button>
        {days.map((day) => (
          <button
            className="secondary"
            key={day.date}
            aria-pressed={selected === day.date}
            onClick={() => select(day.date)}
          >
            Day {day.index + 1}
            <small>{tripDate(day.date)}</small>
          </button>
        ))}
      </div>
      <p id="board-instructions">
        Times are {timeLabel(room)}. Drag a drafting card to a day/time cell, or
        choose the day and time below and use its move button.
      </p>
      <div
        className="gridScroll"
        ref={scroll}
        role="region"
        tabIndex={0}
        aria-label="Scrollable itinerary grid"
      >
        <table aria-describedby="board-instructions">
          <caption>Shared day-by-day itinerary</caption>
          <thead>
            <tr>
              <th scope="col">{timeLabel(room)}</th>
              {visibleDays.map((day) => (
                <th key={day.index} scope="col">
                  Day {day.index + 1}
                  <br />
                  {tripDate(day.date)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {Array.from({ length: 24 }, (_, hour) => (
              <tr key={hour} data-hour={hour}>
                <th scope="row">{String(hour).padStart(2, "0")}:00</th>
                {visibleDays.map((day) => (
                  <td
                    key={day.index}
                    aria-label={`${day.date} ${hour}:00 ${timeLabel(room)}`}
                    onDragOver={(event) => {
                      if (canEdit) event.preventDefault();
                    }}
                    onDrop={(event) => drop(event, day, hour)}
                  >
                    {board.items
                      .filter(
                        (item) =>
                          displayTime(item.startTime, room).slice(0, 10) ===
                            day.date &&
                          Number(
                            displayTime(item.startTime, room).slice(11, 13),
                          ) === hour,
                      )
                      .sort(
                        (a, b) =>
                          a.startTime.localeCompare(b.startTime) ||
                          a.itemId.localeCompare(b.itemId),
                      )
                      .map((item) => (
                        <article
                          className="place gridCard"
                          key={item.itemId}
                          draggable={
                            canEdit && item.lifecycleStage === "drafting"
                          }
                          onDragStart={(event) => {
                            event.dataTransfer.effectAllowed = "move";
                            event.dataTransfer.setData(
                              "application/tripsync-item",
                              JSON.stringify({
                                itemId: item.itemId,
                                positionVersion: item.positionVersion,
                              }),
                            );
                          }}
                        >
                          <div>
                            <Badge tone={item.lifecycleStage}>
                              {item.lifecycleStage}
                            </Badge>
                            <h3>{item.name}</h3>
                            <small>
                              {displayTime(item.startTime, room)}{" "}
                              {timeLabel(room)} –{" "}
                              {displayTime(item.endTime, room).slice(11)}{" "}
                              {timeLabel(room)}
                            </small>
                            <p>
                              {money(item.pricePerPersonMinor, room.currency)} /
                              person
                            </p>
                            <small>
                              {item.attendeeIds.length} travelers ·{" "}
                              {item.splitMode} split
                            </small>
                          </div>
                          <div className="cardActions">
                            {item.lifecycleStage === "drafting" && (
                              <>
                                <button
                                  className="link"
                                  disabled={!canEdit}
                                  onClick={() => onSelectedMove(item)}
                                >
                                  Move to selected time
                                </button>
                                <button
                                  className="link"
                                  disabled={!canEdit}
                                  onClick={() => onRemove(item)}
                                >
                                  Remove
                                </button>
                              </>
                            )}
                            {room.role === "leader" &&
                              item.lifecycleStage === "drafting" && (
                                <button
                                  className="link"
                                  disabled={!canLead}
                                  onClick={() => onLock(item)}
                                >
                                  Lock
                                </button>
                              )}
                            {room.role === "leader" &&
                              item.lifecycleStage === "locked" && (
                                <button
                                  className="link"
                                  disabled={!canLead}
                                  onClick={() => onUnlock(item)}
                                >
                                  Unlock
                                </button>
                              )}
                          </div>
                        </article>
                      ))}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
