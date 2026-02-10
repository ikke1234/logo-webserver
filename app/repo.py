from datetime import datetime, timedelta
from .database import get_connection


def fetchone(sql, params=()):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(sql, params)
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row


def fetchall(sql, params=()):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(sql, params)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def exec_sql(sql, params=()):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(sql, params)
    conn.commit()
    cur.close()
    conn.close()


def exec_many(sql, rows):
    conn = get_connection()
    cur = conn.cursor()
    cur.executemany(sql, rows)
    conn.commit()
    cur.close()
    conn.close()


# ---------- sessions ----------
def create_session(user_id: int, token: str, minutes=480):
    expires = datetime.now() + timedelta(minutes=minutes)
    exec_sql(
        "INSERT INTO sessions (token, user_id, expires_at) VALUES (?, ?, ?)",
        (token, user_id, expires),
    )
    return expires


def get_session(token: str):
    row = fetchone(
        "SELECT s.token, s.expires_at, u.id, u.username, u.role "
        "FROM sessions s JOIN users u ON u.id = s.user_id "
        "WHERE s.token = ?",
        (token,),
    )
    if not row:
        return None
    token, expires_at, uid, username, role = row
    if datetime.now() > expires_at:
        exec_sql("DELETE FROM sessions WHERE token=?", (token,))
        return None
    return {"user_id": uid, "username": username, "role": role}


# ---------- logging ----------
def log_login(username: str | None, success: bool, ip: str | None, ua: str | None, reason: str | None):
    exec_sql(
        "INSERT INTO login_log (username, success, ip, user_agent, reason) VALUES (?,?,?,?,?)",
        (username, int(success), ip, (ua or "")[:200], (reason or "")[:200]),
    )


def bump_login_stats(user_id: int):
    exec_sql(
        "UPDATE users SET login_count = login_count + 1, last_login = GETDATE() WHERE id=?",
        (user_id,),
    )


def log_audit(username: str, action: str):
    exec_sql(
        "INSERT INTO audit_log (username, action) VALUES (?, ?)",
        (username, action[:200]),
    )


# ---------- UI tabs/widgets ----------
def list_tabs_for_user(user_id: int):
    return fetchall(
        "SELECT t.id, t.name, t.sort_order "
        "FROM ui_tabs t "
        "JOIN ui_tab_acl a ON a.tab_id = t.id "
        "WHERE a.user_id = ? AND a.can_view = 1 "
        "ORDER BY t.sort_order",
        (user_id,),
    )


def list_all_tabs():
    return fetchall("SELECT id, name, sort_order FROM ui_tabs ORDER BY sort_order", ())


def list_widgets_for_tabs(tab_ids: list[int]):
    if not tab_ids:
        return []
    placeholders = ",".join(["?"] * len(tab_ids))
    return fetchall(
        f"SELECT id, tab_id, type, title, modbus_kind, address, scale, unit, "
        f"min_value, max_value, default_value, x, y, w, h, writable "
        f"FROM ui_widgets WHERE tab_id IN ({placeholders})",
        tuple(tab_ids),
    )


def upsert_tab(name: str, sort_order: int):
    exec_sql("INSERT INTO ui_tabs (name, sort_order) VALUES (?, ?)", (name, sort_order))


def set_tab_acl(tab_id: int, user_id: int, can_view: bool, can_edit: bool):
    row = fetchone("SELECT id FROM ui_tab_acl WHERE tab_id=? AND user_id=?", (tab_id, user_id))
    if row:
        exec_sql(
            "UPDATE ui_tab_acl SET can_view=?, can_edit=? WHERE tab_id=? AND user_id=?",
            (int(can_view), int(can_edit), tab_id, user_id),
        )
    else:
        exec_sql(
            "INSERT INTO ui_tab_acl (tab_id, user_id, can_view, can_edit) VALUES (?,?,?,?)",
            (tab_id, user_id, int(can_view), int(can_edit)),
        )


def create_widget(w: dict):
    exec_sql(
        "INSERT INTO ui_widgets (tab_id, type, title, modbus_kind, address, scale, unit, "
        "min_value, max_value, default_value, x, y, w, h, writable) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            w["tab_id"],
            w["type"],
            w["title"],
            w["modbus_kind"],
            w["address"],
            w["scale"],
            w.get("unit"),
            w.get("min_value"),
            w.get("max_value"),
            w.get("default_value"),
            w["x"],
            w["y"],
            w["w"],
            w["h"],
            int(w["writable"]),
        ),
    )


def update_widget_positions(items: list[dict]):
    rows = [(int(i["x"]), int(i["y"]), int(i["w"]), int(i["h"]), int(i["id"])) for i in items]
    exec_many("UPDATE ui_widgets SET x=?, y=?, w=?, h=? WHERE id=?", rows)


def delete_widget(widget_id: int):
    exec_sql("DELETE FROM ui_widgets WHERE id=?", (widget_id,))


# ---------- users admin ----------
def list_users():
    return fetchall(
        "SELECT id, username, role, force_pw_change, is_disabled, login_count, last_login "
        "FROM users ORDER BY username",
        (),
    )


def create_user(username: str, pw_hash: str, role: str):
    exec_sql(
        "INSERT INTO users (username, password_hash, role) VALUES (?,?,?)",
        (username, pw_hash, role),
    )
    row = fetchone("SELECT id FROM users WHERE username=?", (username,))
    return int(row[0]) if row else None


def set_user_password(user_id: int, pw_hash: str, force_change: bool):
    exec_sql(
        "UPDATE users SET password_hash=?, force_pw_change=? WHERE id=?",
        (pw_hash, int(force_change), user_id),
    )


def set_user_disabled(user_id: int, disabled: bool):
    exec_sql("UPDATE users SET is_disabled=? WHERE id=?", (int(disabled), user_id))


def set_force_pw_change(user_id: int, force_change: bool):
    exec_sql("UPDATE users SET force_pw_change=? WHERE id=?", (int(force_change), user_id))


def mark_reset_request(username: str, ip: str | None, ua: str | None):
    exec_sql(
        "INSERT INTO password_reset_requests (username, ip, user_agent) VALUES (?,?,?)",
        (username, ip, (ua or "")[:200]),
    )
