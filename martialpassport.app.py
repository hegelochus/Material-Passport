"""Material Passport Database, a Streamlit app.

Run locally:
    pip install streamlit pandas
    streamlit run app.py
"""
import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st

DB_PATH = Path(__file__).with_name("passports.db")
STATUSES = ["GREEN", "YELLOW", "RED"]
ICON = {"GREEN": "🟢", "YELLOW": "🟡", "RED": "🔴"}

# (column, label, placeholder)
FIELDS = [
    ("mission", "Mission / Year", "Mars 2020 / 2021"),
    ("component", "Component", "Perseverance wheel"),
    ("original_function", "Original function", "Mobility / traction"),
    ("material", "Known material", "Aluminum wheel + titanium spokes"),
    ("observed_condition", "Observed condition", "To be assessed from imagery"),
    ("second_life", "Candidate second life", "Mechanical / structural component"),
    ("required_tests", "Required tests", "Composition, fatigue, contamination"),
    ("energy", "Energy / processing", "To be estimated per application"),
    ("safety", "Safety", "Risk assessment required"),
    ("next_decision", "Next decision", "Approve / redirect / final waste"),
]

SEED = [
    dict(mission="Mars 2020 / 2021", component="Perseverance wheel",
         original_function="Mobility / traction",
         material="Aluminum wheel + titanium spokes",
         observed_condition="To be assessed from imagery / future inspection",
         second_life="Mechanical / structural component",
         required_tests="Composition, mechanical integrity, fatigue, contamination",
         energy="To be estimated per application",
         safety="Risk assessment required", status="YELLOW",
         next_decision="Approve / redirect to another use / final waste"),
    dict(mission="Mars 2020 / 2021", component="Landing system parachute",
         original_function="Descent deceleration",
         material="High-performance technical textile",
         observed_condition="Surface-exposed, minor dust contamination",
         second_life="Protective or structural textile",
         required_tests="Tensile strength, permeability, contamination, micro-structure",
         energy="To be estimated per application",
         safety="Risk assessment required", status="YELLOW",
         next_decision="Approve / redirect to another use / final waste"),
]


# ---------- database ----------
def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    cols = ", ".join(f"{c} TEXT" for c, _, _ in FIELDS)
    with db() as con:
        con.execute(
            f"""CREATE TABLE IF NOT EXISTS passports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                {cols},
                status TEXT DEFAULT 'YELLOW',
                image BLOB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"""
        )
        if con.execute("SELECT COUNT(*) FROM passports").fetchone()[0] == 0:
            for row in SEED:
                keys = ", ".join(row)
                marks = ", ".join("?" for _ in row)
                con.execute(f"INSERT INTO passports ({keys}) VALUES ({marks})",
                            list(row.values()))


def load_df() -> pd.DataFrame:
    with db() as con:
        rows = con.execute(
            "SELECT id, " + ", ".join(c for c, _, _ in FIELDS) +
            ", status, created_at, (image IS NOT NULL) AS has_photo "
            "FROM passports ORDER BY id DESC"
        ).fetchall()
    return pd.DataFrame([dict(r) for r in rows])


def get_one(pid: int):
    with db() as con:
        return con.execute("SELECT * FROM passports WHERE id = ?", (pid,)).fetchone()


def insert(values: dict, image: bytes | None):
    keys = list(values) + ["image"]
    marks = ", ".join("?" for _ in keys)
    with db() as con:
        con.execute(f"INSERT INTO passports ({', '.join(keys)}) VALUES ({marks})",
                    list(values.values()) + [image])


def update(pid: int, **changes):
    sets = ", ".join(f"{k} = ?" for k in changes)
    with db() as con:
        con.execute(f"UPDATE passports SET {sets} WHERE id = ?",
                    list(changes.values()) + [pid])


def delete(pid: int):
    with db() as con:
        con.execute("DELETE FROM passports WHERE id = ?", (pid,))


def pid_label(pid: int) -> str:
    return f"MP-{pid:04d}"


# ---------- page ----------
st.set_page_config(page_title="Material Passport Database", page_icon="🪪", layout="wide")
init_db()

st.title("🪪 Material Passport Database")
st.caption("Every recovered material gets a record: traceability instead of guesswork.")

with st.expander("How it works", expanded=False):
    st.markdown(
        """
A **Material Passport** follows a recovered material from its original mission to its next use.
It records where the material came from, what it is made of, its condition, its original function,
possible new applications and the tests required before reuse.

1. **Create**: open the *New passport* tab, fill in the fields, pick a status, optionally add a photo.
2. **Find**: search and filter in the *Database* tab. Counters show totals per status.
3. **Open**: choose a passport in the *Record* tab to see all fields with its photo on the side.
4. **Update**: change the status, replace the photo, or delete the record.

**Status** is about one specific use, never about the material in general:
- 🟢 **GREEN**: qualified for this specific use. It does not mean "safe for everything".
- 🟡 **YELLOW**: has potential, but evidence is lacking. Testing required.
- 🔴 **RED**: should not be used for the proposed purpose. Another use may still work.

A failure in one application is not automatically final waste.
"""
    )

df = load_df()

# stats
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total", len(df))
for col, s in zip((c2, c3, c4), STATUSES):
    col.metric(f"{ICON[s]} {s}", int((df["status"] == s).sum()) if len(df) else 0)

tab_db, tab_new, tab_rec = st.tabs(["📋 Database", "➕ New passport", "🔎 Record"])

# ----- database tab -----
with tab_db:
    f1, f2 = st.columns([3, 1])
    q = f1.text_input("Search", placeholder="component, mission, material, second life…")
    sf = f2.selectbox("Status", ["All"] + STATUSES)

    view = df.copy()
    if len(view):
        if q:
            hay = (view["component"].fillna("") + " " + view["mission"].fillna("") + " " +
                   view["material"].fillna("") + " " + view["second_life"].fillna("")).str.lower()
            view = view[hay.str.contains(q.lower(), regex=False)]
        if sf != "All":
            view = view[view["status"] == sf]

    if view.empty:
        st.info("No passports match. Add one in the *New passport* tab.")
    else:
        show = view.copy()
        show.insert(0, "Passport", show["id"].map(pid_label))
        show["status"] = show["status"].map(lambda s: f"{ICON.get(s, '')} {s}")
        show["photo"] = show["has_photo"].map(lambda x: "📷" if x else "")
        st.dataframe(
            show[["Passport", "component", "mission", "material", "status",
                  "next_decision", "photo"]],
            use_container_width=True, hide_index=True,
        )
        st.download_button("⬇️ Export CSV", view.drop(columns=["has_photo"]).to_csv(index=False),
                           file_name="material_passports.csv", mime="text/csv")

# ----- new passport tab -----
with tab_new:
    with st.form("new_passport", clear_on_submit=True):
        cols = st.columns(2)
        values = {}
        for i, (key, label, ph) in enumerate(FIELDS):
            values[key] = cols[i % 2].text_input(label, placeholder=ph)
        status = st.selectbox("Status", STATUSES, index=1)
        photo = st.file_uploader("Photo (optional)", type=["png", "jpg", "jpeg", "webp"])
        submitted = st.form_submit_button("Save passport", type="primary")
    if submitted:
        if not (values["component"].strip() or values["material"].strip()):
            st.error("Add at least a component or a material.")
        else:
            values = {k: v.strip() for k, v in values.items()}
            values["status"] = status
            insert(values, photo.getvalue() if photo else None)
            st.success("Passport saved.")
            st.rerun()

# ----- record tab -----
with tab_rec:
    if df.empty:
        st.info("Nothing to show yet.")
    else:
        ids = df["id"].tolist()
        pid = st.selectbox(
            "Choose a passport", ids,
            format_func=lambda i: f"{pid_label(i)} · {df.loc[df['id'] == i, 'component'].iloc[0] or 'Untitled'}",
        )
        rec = get_one(pid)
        left, right = st.columns([3, 1])

        with left:
            st.subheader(f"{pid_label(pid)} · {rec['component'] or 'Untitled'}")
            for key, label, _ in FIELDS:
                st.markdown(f"**{label}:** {rec[key] or '–'}")

            st.markdown("---")
            new_status = st.radio("Status", STATUSES, index=STATUSES.index(rec["status"]),
                                  horizontal=True, key=f"st_{pid}")
            if new_status != rec["status"]:
                update(pid, status=new_status)
                st.rerun()

            with st.popover("🗑️ Delete this passport"):
                st.warning("This cannot be undone.")
                if st.button("Yes, delete", key=f"del_{pid}"):
                    delete(pid)
                    st.rerun()

        with right:
            if rec["image"]:
                st.image(rec["image"], use_container_width=True)
            else:
                st.info("No photo yet")
            up = st.file_uploader("Add / replace photo", type=["png", "jpg", "jpeg", "webp"],
                                  key=f"img_{pid}")
            if up and st.button("Save photo", key=f"sv_{pid}"):
                update(pid, image=up.getvalue())
                st.rerun()
