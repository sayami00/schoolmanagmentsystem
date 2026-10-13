"use strict";

const dateInput = document.getElementById("date");

function statTile(label, value, dot, hint = "", hero = false) {
  return `<div class="stat${hero ? " hero" : ""}">
    <div class="label">${dot ? `<span class="dot ${dot}"></span>` : ""}${esc(label)}</div>
    <div class="value">${esc(value)}</div>${hint ? `<div class="hint">${esc(hint)}</div>` : ""}</div>`;
}

function renderStats(s) {
  document.getElementById("stats").innerHTML = [
    statTile("Attendance rate", fmtRate(s.attendance_rate), "", `${s.marked} of ${s.headcount} marked`, true),
    statTile("Active staff", s.headcount, "", `${s.departments} departments`),
    statTile("Present", s.present, "good"),
    statTile("Late", s.late, "warn"),
    statTile("Half day", s.half_day, "info"),
    statTile("Absent", s.absent, "bad"),
    statTile("On leave", s.on_leave, "leave"),
    statTile("Not marked", s.not_marked, "none"),
    statTile("Pending leave", s.pending_leaves, "", "awaiting review"),
  ].join("");
}

function renderTrend(trend, selected) {
  const box = document.getElementById("trend");
  const cols = trend.map((t) => {
    const pct = t.attendance_rate ?? 0;
    const label = t.attendance_rate === null ? "—" : `${Math.round(t.attendance_rate)}%`;
    return `<div class="col" tabindex="0" data-date="${t.date}" aria-label="${esc(fmtDate(t.date))}: ${esc(label)}">
      <span class="val">${esc(label)}</span><div class="bar" data-h="${pct}"></div></div>`;
  }).join("");
  const labels = trend.map((t) => `<span>${esc(
    fmtDate(t.date, { weekday: "short", day: "numeric" }))}</span>`).join("");
  box.innerHTML = `<div class="cols">${cols}</div><div class="col-labels">${labels}</div>`;

  box.querySelectorAll(".col").forEach((col, i) => {
    const t = trend[i];
    // Heights set through CSSOM, which the CSP allows (inline style attributes are blocked).
    col.querySelector(".bar").style.height = `${Number(col.querySelector(".bar").dataset.h)}%`;
    attachTooltip(col, `<strong>${esc(fmtDate(t.date, { weekday: "long", day: "numeric", month: "short" }))}</strong><br>
      Rate: ${esc(fmtRate(t.attendance_rate))}<br>Marked: ${t.marked} of ${t.headcount}`);
  });
}

function renderDepartments(depts) {
  const bars = document.getElementById("dept-bars");
  bars.innerHTML = depts.map((d) => `<div class="hbar" tabindex="0">
      <span class="name" title="${esc(d.name)}">${esc(d.name)}</span>
      <div class="track"><div class="fill"></div></div>
      <span class="v">${esc(fmtRate(d.attendance_rate))}</span></div>`).join("")
    || '<p class="muted">No departments yet.</p>';
  bars.querySelectorAll(".hbar").forEach((row, i) => {
    const d = depts[i];
    row.querySelector(".fill").style.width = `${d.attendance_rate ?? 0}%`;
    attachTooltip(row, `<strong>${esc(d.name)}</strong><br>Staff: ${d.headcount} · Marked: ${d.marked}<br>
      Present ${d.present} · Late ${d.late} · Half ${d.half_day}<br>Absent ${d.absent} · Leave ${d.on_leave}`);
  });

  document.getElementById("dept-table").innerHTML = depts.map((d) => `<tr>
      <td data-label="Department">${esc(d.name)}</td>
      <td data-label="Staff" class="num">${d.headcount}</td>
      <td data-label="Present" class="num">${d.present}</td>
      <td data-label="Late" class="num">${d.late}</td>
      <td data-label="Half day" class="num">${d.half_day}</td>
      <td data-label="Absent" class="num">${d.absent}</td>
      <td data-label="Leave" class="num">${d.on_leave}</td>
      <td data-label="Not marked" class="num">${d.not_marked}</td></tr>`).join("")
    || '<tr><td colspan="8" class="empty">No departments yet.</td></tr>';
}

function renderLeaves(leaves) {
  document.getElementById("recent-leaves").innerHTML = leaves.map((l) => `<li>
      <div><strong>${esc(l.employee_name)}</strong>
        <span class="sub muted">${esc(LEAVE_TYPES[l.leave_type])} · ${esc(fmtDate(l.start_date))}${
          l.end_date !== l.start_date ? ` – ${esc(fmtDate(l.end_date))}` : ""}</span></div>
      ${badge(l.status, l.status[0].toUpperCase() + l.status.slice(1))}</li>`).join("")
    || '<li class="muted">No leave records yet.</li>';
}

async function load() {
  const data = await api(`/api/dashboard${qs({ date: dateInput.value })}`);
  document.getElementById("date-label").textContent = fmtDate(data.date, { weekday: "long", day: "numeric", month: "long", year: "numeric" });
  document.getElementById("mark-link").href = `/attendance?date=${encodeURIComponent(data.date)}`;
  renderStats(data.summary);
  renderTrend(data.trend, data.date);
  renderDepartments(data.departments);
  renderLeaves(data.recent_leaves);
}

onReady(async () => {
  await initLayout();
  dateInput.value = todayISO();
  dateInput.max = todayISO();
  dateInput.addEventListener("change", () => load().catch((e) => toast(e.message, "error")));
  await load();
});
