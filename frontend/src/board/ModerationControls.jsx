import React from "react";

export default function ModerationControls({
  members,
  userId,
  connectedUsers,
  roomLocked,
  enabled,
  onCommand,
}) {
  function confirm(action, member) {
    const message =
      action === "remove"
        ? `Remove ${member.displayName} from this trip? Their open room sessions will close.`
        : `Make ${member.displayName} the trip Leader? You will become a Planner.`;
    if (window.confirm(message)) onCommand(action, member.userId);
  }
  return (
    <section
      className="panel inviteControls"
      id="room-controls"
      aria-label="Leader moderation"
    >
      <h2>Room controls</h2>
      <p>
        {roomLocked
          ? "The board is locked. Members can still read and chat."
          : "The board is open for planning."}
      </p>
      <button
        className="secondary"
        disabled={!enabled}
        onClick={() => onCommand(roomLocked ? "unlockRoom" : "lockRoom")}
      >
        {roomLocked ? "Unlock room" : "Lock room"}
      </button>
      <h3>Manage travelers</h3>
      {members
        .filter((member) => member.userId !== userId)
        .map((member) => (
          <div key={member.userId} className="place">
            <div>
              <strong>{member.displayName}</strong>
              <p>
                {member.role}
                {member.muted ? " · Muted" : ""}
              </p>
            </div>
            <div>
              <button
                className="link"
                disabled={!enabled}
                onClick={() =>
                  onCommand(member.muted ? "unmute" : "mute", member.userId)
                }
              >
                {member.muted ? "Unmute" : "Mute"} {member.displayName}
              </button>
              <button
                className="link"
                disabled={!enabled}
                onClick={() => confirm("remove", member)}
              >
                Remove {member.displayName}
              </button>
              {member.role === "planner" && (
                <button
                  className="link"
                  disabled={!enabled || !connectedUsers.includes(member.userId)}
                  onClick={() => confirm("transfer", member)}
                >
                  Make {member.displayName} Leader
                </button>
              )}
            </div>
          </div>
        ))}
    </section>
  );
}
