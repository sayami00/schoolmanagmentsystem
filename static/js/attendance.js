"use strict";

const el = (id) => document.getElementById(id);
const NO_TIME = new Set(["absent", "on_leave"]);
let sheet = { items: [], editable: true };

function statusOptions(selected) {
  return '<option value="">— Not marked —</option>' + Object.entries(STATUS_LABELS)
    .map(([v, l]) => `<option value="${v}"${v === selected ? " selected" : ""}>${esc(l)}</option>`).join("");
}

function render() {
  const dis = sheet.editable ? "" : " disabled";
  el("rows").innerHTML = sheet.items.map((r, i) => {
    // Employees on approved leave default to "On leave" until a record is saved.
    const status = r.status || (r.leave_type ? "on_leave" : "");
    const leaveNote = r.leave_type ? `<span class="sub">Approved ${esc(LEAVE_TYPES[r.leave_type].toLowerCase())} leave</span>` : "";
    const noTime = NO_TIME.has(status) ? " disabled" : "";
    return `<tr data-i="${i}"${!r.status && status ? ' class="prefill"' : ""}>
      <td data-label="Employee"><strong>${esc(r.name)}</strong>
        <span class="sub">${esc(r.emp_code)} · ${esc(r.department_name)}</span>${leaveNote}</td>
      <td data-label="Status"><select class="status" aria-label="Status for ${esc(r.name)}"${dis}>${statusOptions(status)}</select></td>
      <td data-label="Check-in"><input class="time" type="time" data-f="check_in" value="${esc(r.check_in || "")}" aria-label="Check-in for ${esc(r.name)}"${dis}${noTime}></td>
      <td data-label="Check-out"><input class="time" type="time" data-f="check_out" value="${esc(r.check_out || "")}" aria-label="Check-out for ${esc(r.name)}"${dis}${noTime}></td>
      <td data-label="Notes"><input class="notes" data-f="notes" maxlength="500" value="${esc(r.notes || "")}" aria-label="Notes for ${esc(r.name)}"${dis}></td>
      <td class="actions-cell">${r.record_id && sheet.editable
        ? `<button class="btn sm danger" type="button" data-clear="${r.record_id}">Clear</button>` : ""}</td></tr>`;
  }).join("") || '<tr><td colspan="6" class="empty">No active employees for this date and department.</td></tr>';
  updateSummary();
}

function rowValues(tr) {
  return {
    status: tr.querySelector(".status").value,
    check_in: tr.querySelector('[data-f="check_in"]').value || null,
    check_out: tr.querySelector('[data-f="check_out"]').value || null,
    notes: tr.querySelector('[data-f="notes"]').value.trim(),
  };
}

function updateSummary() {
  const counts = {};
  let unmarked = 0;
  el("rows").querySelectorAll("tr[data-i]").forEach((tr) => {
    const s = tr.querySelector(".status").value;
    if (s) counts[s] = (counts[s] || 0) + 1; else unmarked += 1;
  });
  const parts = Object.entries(STATUS_LABELS).filter(([k]) => counts[k]).map(([k, l]) => `${l} ${counts[k]}`);
  parts.push(`Not marked ${unmarked}`);
  el("summary").textContent = `${fmtDate(el("date").value, { weekday: "long", day: "numeric", month: "long", year: "numeric" })} · ${parts.join(" · ")}`;
}

async function load() {
  const date = el("date").value;
  sheet = await api(`/api/attendance${qs({ date, department_id: el("f-dept").value })}`);
  el("readonly-note").classList.toggle("hidden", sheet.editable);
  el("save").disabled = el("all-present").disabled = !sheet.editable;
  const url = new URL(window.location);
  url.searchParams.set("date", date);
  history.replaceState(null, "", url);
  render();
}

async function save() {
  const records = [];
  for (const tr of el("rows").querySelectorAll("tr[data-i]")) {
    const v = rowValues(tr);
    if (!v.status) continue;
    const item = sheet.items[Number(tr.dataset.i)];
    if (v.check_in && v.check_out && v.check_out <= v.check_in) {
      toast(`${item.name}: check-out must be later than check-in`, "error");
      tr.querySelector('[data-f="check_out"]').focus();
      return;
    }
    records.push({ employee_id: item.employee_id, ...v });
  }
  if (!records.length) { toast("Nothing to save — set a status for at least one employee.", "error"); return; }
  el("save").disabled = true;
  try {
    const res = await api("/api/attendance", { method: "PUT", body: { date: el("date").value, records } });
    toast(`Saved ${res.saved} attendance record${res.saved === 1 ? "" : "s"}`);
    await load();
  } catch (err) {
    toast(err.message, "error");
  } finally {
    el("save").disabled = !sheet.editable;
  }
}

onReady(async () => {
  await initLayout();
  await loadDepartmentOptions(el("f-dept"), { includeAll: true });
  const requested = new URLSearchParams(window.location.search).get("date");
  el("date").value = /^\d{4}-\d{2}-\d{2}$/.test(requested || "") ? requested : todayISO();
  el("date").max = todayISO();

  el("date").addEventListener("change", () => load().catch((e) => toast(e.message, "error")));
  el("f-dept").addEventListener("change", () => load().catch((e) => toast(e.message, "error")));
  el("save").addEventListener("click", save);

  el("all-present").addEventListener("click", () => {
    el("rows").querySelectorAll("tr[data-i]").forEach((tr) => {
      const sel = tr.querySelector(".status");
      if (!sel.value) { sel.value = "present"; sel.dispatchEvent(new Event("change", { bubbles: true })); }
    });
  });

  el("rows").addEventListener("change", (e) => {
    const tr = e.target.closest("tr[data-i]");
    if (!tr) return;
    tr.classList.add("dirty");
    if (e.target.classList.contains("status")) {
      const noTime = NO_TIME.has(e.target.value);
      tr.querySelectorAll(".time").forEach((inp) => { inp.disabled = noTime; if (noTime) inp.value = ""; });
      updateSummary();
    }
  });

  el("rows").addEventListener("click", async (e) => {
    const id = e.target.closest("[data-clear]")?.dataset.clear;
    if (!id) return;
    if (!(await confirmDialog("Remove this saved attendance record?", { okLabel: "Remove" }))) return;
    try {
      await api(`/api/attendance/${id}`, { method: "DELETE" });
      toast("Record removed");
      await load();
    } catch (err) { toast(err.message, "error"); }
  });

  window.addEventListener("beforeunload", (e) => {
    if (el("rows").querySelector("tr.dirty")) e.preventDefault();
  });
  await load();
});
