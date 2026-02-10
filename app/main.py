from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import secrets

from passlib.context import CryptContext

from app import repo
from app.modbus_dynamic import read_points, get_plc_status
from app.logo_modbus_map import translate
from app.modbus import write_register, write_coil

app = FastAPI(title="Logo Gateway")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ---------------- helpers ----------------
def get_session_or_401(token: str):
    s = repo.get_session(token)
    if not s:
        raise HTTPException(401, "Ongeldige of verlopen sessie")
    return s


def require_admin(s):
    if s["role"] != "admin":
        raise HTTPException(403, "Admin rechten nodig")


def can_view_tab(s, tab_id: int) -> bool:
    if s["role"] == "admin":
        return True
    row = repo.fetchone("SELECT can_view FROM ui_tab_acl WHERE tab_id=? AND user_id=?", (tab_id, s["user_id"]))
    return bool(row and int(row[0]) == 1)


def can_edit_tab(s, tab_id: int) -> bool:
    if s["role"] == "admin":
        return True
    row = repo.fetchone("SELECT can_edit FROM ui_tab_acl WHERE tab_id=? AND user_id=?", (tab_id, s["user_id"]))
    return bool(row and int(row[0]) == 1)


# ---------------- models ----------------
class LoginRequest(BaseModel):
    username: str
    password: str


class ForgotPasswordRequest(BaseModel):
    username: str


class ChangePasswordRequest(BaseModel):
    token: str
    old_password: str
    new_password: str


class WritePoint(BaseModel):
    token: str
    tab_id: int
    widget_id: int
    value: float | bool


class AdminCreateUser(BaseModel):
    token: str
    username: str
    password: str
    role: str  # viewer/editor (geen admin)


class AdminResetPassword(BaseModel):
    token: str
    user_id: int
    temp_password: str
    force_change: bool = True


class AdminDisableUser(BaseModel):
    token: str
    user_id: int
    disabled: bool


class AdminForcePW(BaseModel):
    token: str
    user_id: int
    force_change: bool


class AdminTab(BaseModel):
    token: str
    name: str
    sort_order: int = 10


class AdminWidget(BaseModel):
    token: str
    tab_id: int
    type: str
    title: str

    # LOGO mapping optie
    logo_resource: str | None = None
    logo_index: str | None = None

    # raw optie
    modbus_kind: str | None = None  # holding/input/coil/di
    address: int | None = None

    scale: float = 1.0
    unit: str | None = None
    min_value: float | None = None
    max_value: float | None = None
    default_value: float | None = None
    x: int = 1
    y: int = 1
    w: int = 1
    h: int = 1
    writable: bool = False


class AdminLayoutItem(BaseModel):
    id: int
    x: int
    y: int
    w: int
    h: int


class AdminSaveLayout(BaseModel):
    token: str
    items: list[AdminLayoutItem]


class AdminAcl(BaseModel):
    token: str
    tab_id: int
    user_id: int
    can_view: bool
    can_edit: bool


# ---------------- auth endpoints ----------------
@app.post("/api/login")
def api_login(body: LoginRequest, request: Request):
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent", "")

    row = repo.fetchone(
        "SELECT id, password_hash, role, is_disabled, force_pw_change FROM users WHERE username=?",
        (body.username,),
    )
    if not row:
        repo.log_login(body.username, False, ip, ua, "user_not_found")
        raise HTTPException(401, "Login fout")

    user_id, pw_hash, role, is_disabled, force_pw_change = row

    if int(is_disabled) == 1:
        repo.log_login(body.username, False, ip, ua, "disabled")
        raise HTTPException(403, "Account uitgeschakeld")

    if not pwd.verify(body.password, pw_hash):
        repo.log_login(body.username, False, ip, ua, "bad_password")
        raise HTTPException(401, "Login fout")

    token = secrets.token_hex(32)
    repo.create_session(int(user_id), token, minutes=480)

    repo.log_login(body.username, True, ip, ua, None)
    repo.bump_login_stats(int(user_id))
    repo.log_audit(body.username, "LOGIN")

    return {
        "token": token,
        "role": role,
        "username": body.username,
        "force_pw_change": bool(force_pw_change),
    }


@app.post("/api/forgot_password")
def api_forgot_password(body: ForgotPasswordRequest, request: Request):
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent", "")
    repo.mark_reset_request(body.username, ip, ua)
    repo.log_audit(body.username, "FORGOT_PASSWORD_REQUEST")
    # altijd “OK” teruggeven (geen user-enumeration)
    return {"status": "ok"}


@app.post("/api/change_password")
def api_change_password(body: ChangePasswordRequest):
    s = get_session_or_401(body.token)

    row = repo.fetchone("SELECT password_hash FROM users WHERE id=?", (s["user_id"],))
    if not row:
        raise HTTPException(404, "User niet gevonden")
    pw_hash = row[0]

    if not pwd.verify(body.old_password, pw_hash):
        raise HTTPException(401, "Oud wachtwoord fout")

    new_hash = pwd.hash(body.new_password)
    repo.set_user_password(s["user_id"], new_hash, False)
    repo.log_audit(s["username"], "CHANGE_PASSWORD")
    return {"status": "ok"}


# ---------------- UI endpoints ----------------
@app.get("/api/ui")
def api_ui(token: str):
    s = get_session_or_401(token)

    if s["role"] == "admin":
        tabs = repo.list_all_tabs()
    else:
        tabs = repo.list_tabs_for_user(s["user_id"])

    tab_list = [{"id": t[0], "name": t[1], "sort_order": int(t[2])} for t in tabs]
    tab_ids = [t["id"] for t in tab_list]

    widgets = repo.list_widgets_for_tabs(tab_ids)
    widget_list = []
    for w in widgets:
        widget_list.append(
            {
                "id": int(w[0]),
                "tab_id": int(w[1]),
                "type": w[2],
                "title": w[3],
                "modbus_kind": w[4],
                "address": int(w[5]),
                "scale": float(w[6] or 1.0),
                "unit": w[7],
                "min_value": w[8],
                "max_value": w[9],
                "default_value": w[10],
                "x": int(w[11]),
                "y": int(w[12]),
                "w": int(w[13]),
                "h": int(w[14]),
                "writable": bool(w[15]),
            }
        )

    return {"tabs": tab_list, "widgets": widget_list, "role": s["role"]}


@app.get("/api/values")
def api_values(token: str, tab_id: int):
    s = get_session_or_401(token)

    if not can_view_tab(s, tab_id):
        raise HTTPException(403, "Geen toegang")

    rows = repo.fetchall(
        "SELECT id, modbus_kind, address, scale, default_value FROM ui_widgets WHERE tab_id=?",
        (tab_id,),
    )

    points = []
    for r in rows:
        points.append(
            {
                "id": int(r[0]),
                "modbus_kind": r[1],
                "address": int(r[2]),
                "scale": float(r[3] or 1.0),
                "default": r[4],
            }
        )

    values = read_points(points)
    plc = get_plc_status()
    return {"values": values, "plc": plc}


@app.post("/api/write")
def api_write(body: WritePoint):
    s = get_session_or_401(body.token)

    if not can_edit_tab(s, body.tab_id):
        raise HTTPException(403, "Geen edit rechten")

    w = repo.fetchone(
        "SELECT modbus_kind, address, writable, scale FROM ui_widgets WHERE id=? AND tab_id=?",
        (body.widget_id, body.tab_id),
    )
    if not w:
        raise HTTPException(404, "Widget niet gevonden")

    kind, address, writable, scale = w
    if int(writable) != 1:
        raise HTTPException(403, "Widget is read-only")

    address = int(address)
    scale = float(scale or 1.0)

    if kind == "holding":
        if scale == 0:
            raise HTTPException(400, "Scale mag niet 0 zijn")
        v = float(body.value)
        raw = int(round(v / scale))
        write_register(address, raw)
        repo.log_audit(s["username"], f"WRITE holding addr={address} raw={raw} val={v}")
        return {"status": "ok", "raw": raw}

    if kind == "coil":
        b = bool(body.value)
        write_coil(address, b)
        repo.log_audit(s["username"], f"WRITE coil addr={address} val={b}")
        return {"status": "ok"}

    raise HTTPException(400, "Niet schrijfbaar type")


# ---------------- admin: users ----------------
@app.get("/api/admin/users")
def admin_users(token: str):
    s = get_session_or_401(token)
    require_admin(s)

    rows = repo.list_users()
    return {
        "users": [
            {
                "id": int(r[0]),
                "username": r[1],
                "role": r[2],
                "force_pw_change": bool(r[3]),
                "is_disabled": bool(r[4]),
                "login_count": int(r[5]),
                "last_login": (str(r[6]) if r[6] else None),
            }
            for r in rows
        ]
    }


@app.post("/api/admin/user")
def admin_create_user(body: AdminCreateUser):
    s = get_session_or_401(body.token)
    require_admin(s)

    role = body.role.lower().strip()
    if role not in ("viewer", "editor"):
        raise HTTPException(400, "Rol moet viewer of editor zijn (geen admin)")

    pw_hash = pwd.hash(body.password)
    uid = repo.create_user(body.username, pw_hash, role)
    repo.set_force_pw_change(uid, True)  # nieuwe users moeten wijzigen
    repo.log_audit(s["username"], f"ADD USER {body.username} role={role}")

    return {"status": "ok", "user_id": uid}


@app.post("/api/admin/user/reset_password")
def admin_reset_password(body: AdminResetPassword):
    s = get_session_or_401(body.token)
    require_admin(s)

    new_hash = pwd.hash(body.temp_password)
    repo.set_user_password(body.user_id, new_hash, body.force_change)
    repo.log_audit(s["username"], f"RESET PASSWORD user_id={body.user_id} force={body.force_change}")
    return {"status": "ok"}


@app.post("/api/admin/user/disable")
def admin_disable_user(body: AdminDisableUser):
    s = get_session_or_401(body.token)
    require_admin(s)

    repo.set_user_disabled(body.user_id, body.disabled)
    repo.log_audit(s["username"], f"DISABLE USER user_id={body.user_id} disabled={body.disabled}")
    return {"status": "ok"}


@app.post("/api/admin/user/force_pw_change")
def admin_force_pw(body: AdminForcePW):
    s = get_session_or_401(body.token)
    require_admin(s)

    repo.set_force_pw_change(body.user_id, body.force_change)
    repo.log_audit(s["username"], f"FORCE PW CHANGE user_id={body.user_id} force={body.force_change}")
    return {"status": "ok"}


# ---------------- admin: tabs / acl ----------------
@app.post("/api/admin/tab")
def admin_add_tab(body: AdminTab):
    s = get_session_or_401(body.token)
    require_admin(s)

    repo.upsert_tab(body.name, body.sort_order)
    repo.log_audit(s["username"], f"ADD TAB {body.name}")
    return {"status": "ok"}


@app.post("/api/admin/tab_acl")
def admin_set_acl(body: AdminAcl):
    s = get_session_or_401(body.token)
    require_admin(s)

    repo.set_tab_acl(body.tab_id, body.user_id, body.can_view, body.can_edit)
    repo.log_audit(
        s["username"],
        f"SET ACL tab={body.tab_id} user={body.user_id} view={body.can_view} edit={body.can_edit}",
    )
    return {"status": "ok"}


# ---------------- admin: widgets / dragdrop layout ----------------
@app.post("/api/admin/widget")
def admin_add_widget(body: AdminWidget):
    s = get_session_or_401(body.token)
    require_admin(s)

    if body.logo_resource and body.logo_index:
        t = translate(body.logo_resource, body.logo_index)
        modbus_kind = t["modbus_kind"]
        address = int(t["address"])
    else:
        if not body.modbus_kind or body.address is None:
            raise HTTPException(400, "Geen address info")
        modbus_kind = body.modbus_kind
        address = int(body.address)

    repo.create_widget(
        {
            "tab_id": body.tab_id,
            "type": body.type,
            "title": body.title,
            "modbus_kind": modbus_kind,
            "address": address,
            "scale": float(body.scale),
            "unit": body.unit,
            "min_value": body.min_value,
            "max_value": body.max_value,
            "default_value": body.default_value,
            "x": body.x,
            "y": body.y,
            "w": body.w,
            "h": body.h,
            "writable": bool(body.writable),
        }
    )

    repo.log_audit(s["username"], f"ADD WIDGET tab={body.tab_id} kind={modbus_kind} addr={address}")
    return {"status": "ok", "modbus_kind": modbus_kind, "address": address}


@app.post("/api/admin/widgets/layout")
def admin_save_layout(body: AdminSaveLayout):
    s = get_session_or_401(body.token)
    require_admin(s)

    repo.update_widget_positions([i.dict() for i in body.items])
    repo.log_audit(s["username"], f"SAVE LAYOUT items={len(body.items)}")
    return {"status": "ok"}


@app.post("/api/admin/widget/delete")
def admin_delete_widget(token: str, widget_id: int):
    s = get_session_or_401(token)
    require_admin(s)

    repo.delete_widget(widget_id)
    repo.log_audit(s["username"], f"DELETE WIDGET id={widget_id}")
    return {"status": "ok"}
