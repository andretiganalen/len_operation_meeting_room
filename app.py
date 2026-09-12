import json
import os
from datetime import date, datetime, time, timedelta
from typing import List, Optional

from fastapi import Depends, FastAPI, Form, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
import uvicorn
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
    create_engine,
    text,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker, Session

# --- CLOUD & LOCAL DATABASE CONFIGURATION ---
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./meeting_rooms.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class AppSetting(Base):
    __tablename__ = "app_settings"
    key = Column(String, primary_key=True)
    value = Column(Text, default="")


class BuildingGroup(Base):
    __tablename__ = "building_groups"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    display_order = Column(Integer, default=0)
    rooms = relationship("Room", back_populates="group", cascade="all, delete-orphan", order_by="Room.display_order")


class Room(Base):
    __tablename__ = "rooms"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    group_id = Column(Integer, ForeignKey("building_groups.id"), nullable=False)
    display_order = Column(Integer, default=0)
    is_paused = Column(Boolean, default=False)
    image_url = Column(String, default="")
    facilities = Column(Text, default="")

    group = relationship("BuildingGroup", back_populates="rooms")
    bookings = relationship("Booking", back_populates="room", cascade="all, delete-orphan")


class Booking(Base):
    __tablename__ = "bookings"
    id = Column(Integer, primary_key=True, index=True)
    room_id = Column(Integer, ForeignKey("rooms.id"), nullable=False)
    booking_date = Column(Date, nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    booked_by = Column(String, nullable=False)
    agenda = Column(String, nullable=False)
    department = Column(String, nullable=False)

    room = relationship("Room", back_populates="bookings")


Base.metadata.create_all(bind=engine)


def run_sqlite_migrations():
    if "sqlite" in DATABASE_URL:
        with engine.connect() as conn:
            r_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(rooms)")).fetchall()]
            if "image_url" not in r_cols:
                conn.execute(text("ALTER TABLE rooms ADD COLUMN image_url VARCHAR DEFAULT ''"))
            if "facilities" not in r_cols:
                conn.execute(text("ALTER TABLE rooms ADD COLUMN facilities TEXT DEFAULT ''"))
            if "display_order" not in r_cols:
                conn.execute(text("ALTER TABLE rooms ADD COLUMN display_order INTEGER DEFAULT 0"))

            g_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(building_groups)")).fetchall()]
            if "display_order" not in g_cols:
                conn.execute(text("ALTER TABLE building_groups ADD COLUMN display_order INTEGER DEFAULT 0"))
            conn.commit()


run_sqlite_migrations()


def get_setting(db: Session, key: str, default: str = "") -> str:
    setting = db.query(AppSetting).filter(AppSetting.key == key).first()
    return setting.value if setting else default


def set_setting(db: Session, key: str, value: str):
    setting = db.query(AppSetting).filter(AppSetting.key == key).first()
    if not setting:
        setting = AppSetting(key=key, value=value)
        db.add(setting)
    else:
        setting.value = value
    db.commit()


def init_seed_data():
    db = SessionLocal()
    defaults = {
        "logo_url": "https://via.placeholder.com/140x40/transparent/dc2626?text=COMPANY+LOGO",
        "logo_link": "https://google.com",
        "footer_desc": "© 2026 Enterprise Meeting Room System • Operational Hours: 07:00 - 18:00",
        "app_title": "Meeting Room Booking Grid",
        "btn_book_label": "☰ Book Room",
        "btn_dashboard_label": "📊 Today Dashboard",
        "btn_manual_label": "📄 Blank Manual Sheet",
        "vacant_label": "Vacant",
        "drawer_title": "Book Meeting Room",
    }
    for k, v in defaults.items():
        if not db.query(AppSetting).filter(AppSetting.key == k).first():
            set_setting(db, k, v)

    if db.query(BuildingGroup).count() == 0:
        b_a = BuildingGroup(name="Building A", display_order=1)
        b_b = BuildingGroup(name="Building B", display_order=2)
        b_c = BuildingGroup(name="Building C", display_order=3)
        db.add_all([b_a, b_b, b_c])
        db.commit()

        rooms_data = [
            ("Room 101", b_a.id, 1, "Projector, Whiteboard, 10 Chairs", "https://images.unsplash.com/photo-1497366216548-37526070297c?w=600"),
            ("Room 102", b_a.id, 2, "TV Monitor, Video Conference, 8 Chairs", ""),
            ("Room 103", b_a.id, 3, "Standard Boardroom, 12 Chairs", ""),
            ("Room 104", b_a.id, 4, "Discussion Table, 6 Chairs", ""),
            ("Room 105", b_a.id, 5, "Whiteboard, 8 Chairs", ""),
            ("Room 106", b_a.id, 6, "Screen, 10 Chairs", ""),
            ("Room 201", b_b.id, 1, "Smart TV, Sound System, 14 Chairs", ""),
            ("Room 202", b_b.id, 2, "Projector, AC, 8 Chairs", ""),
            ("Room 203", b_b.id, 3, "Meeting Pod, 4 Chairs", ""),
            ("Room 204", b_b.id, 4, "Executive Setup, 12 Chairs", ""),
            ("Room 205", b_b.id, 5, "Standard Table, 6 Chairs", ""),
            ("Room 206", b_b.id, 6, "Discussion Room, 8 Chairs", ""),
            ("Room 207", b_b.id, 7, "Focus Room, 4 Chairs", ""),
            ("Boardroom B", b_b.id, 8, "4K Display, PTZ Camera, 20 Chairs", "https://images.unsplash.com/photo-1517502884422-41eaead166d4?w=600"),
            ("Room 301", b_c.id, 1, "Standard Room, 10 Chairs", ""),
            ("Room 302", b_c.id, 2, "Projector, 12 Chairs", ""),
            ("Room 303", b_c.id, 3, "TV Screen, 8 Chairs", ""),
            ("Room 304", b_c.id, 4, "Video Bar, 6 Chairs", ""),
            ("Innovation Lab", b_c.id, 5, "Interactive Whiteboard, 16 Chairs", ""),
            ("Auditorium", b_c.id, 6, "Full Stage Audio/Visual, 50 Chairs", ""),
        ]
        for name, gid, ord_idx, fac, img in rooms_data:
            db.add(Room(name=name, group_id=gid, display_order=ord_idx, facilities=fac, image_url=img))
        db.commit()
    db.close()


init_seed_data()

SLOTS = []
cur_dt = datetime.combine(date.today(), time(7, 0))
end_dt = datetime.combine(date.today(), time(18, 0))
while cur_dt < end_dt:
    s_str = cur_dt.strftime("%H:%M")
    nxt = cur_dt + timedelta(minutes=30)
    e_str = nxt.strftime("%H:%M")
    SLOTS.append((s_str, e_str))
    cur_dt = nxt

app = FastAPI()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user_role(request: Request) -> Optional[str]:
    return request.cookies.get("user_role")


BASE_CSS = """
:root {
    --primary-red: #dc2626;
    --primary-red-hover: #b91c1c;
    --vacant-font: #9ca3af;
    --border-color: #e5e7eb;
    --header-bg: #ffffff;
}
* { box-sizing: border-box; font-family: Arial, Helvetica, sans-serif !important; }
body { margin: 0; background: #f8fafc; color: #1e293b; padding-bottom: 90px; }

header {
    background: var(--header-bg); border-bottom: 2px solid #fee2e2; padding: 10px 18px;
    display: flex; justify-content: space-between; align-items: center;
    position: sticky; top: 0; z-index: 50; box-shadow: 0 1px 4px rgba(0,0,0,0.05);
}
.header-left { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.header-logo { height: 38px; max-width: 160px; object-fit: contain; cursor: pointer; }
.header-actions { display: flex; align-items: center; gap: 10px; font-size: 13px; }

.btn { 
    background: var(--primary-red); color: white; border: none; padding: 8px 14px; 
    border-radius: 6px; cursor: pointer; font-weight: bold; text-decoration: none; 
    display: inline-flex; align-items: center; justify-content: center; font-size: 12px;
}
.btn:hover { background: var(--primary-red-hover); }
.btn-outline { background: transparent; border: 1px solid var(--primary-red); color: var(--primary-red); }
.btn-outline:hover { background: #fef2f2; }
.btn-gold { background: #d97706; color: white; }

.day-card { background: white; margin: 16px auto; width: 98%; border-radius: 8px; border: 1px solid #e2e8f0; box-shadow: 0 1px 3px rgba(0,0,0,0.04); overflow: hidden; }
.day-header { background: #fff1f2; color: #991b1b; padding: 10px 16px; font-weight: bold; font-size: 1rem; border-bottom: 1px solid #fecdd3; }
.table-wrap { overflow-x: auto; -webkit-overflow-scrolling: touch; }
table { border-collapse: collapse; width: 100%; font-size: 11px; text-align: center; }
th, td { border: 1px solid var(--border-color); padding: 4px; min-width: 90px; height: 35px; }
th.time-col, td.time-col { min-width: 80px; font-weight: bold; background: #fff; position: sticky; left: 0; z-index: 10; border-right: 2px solid #e2e8f0; }

.slot-vacant { background-color: #ffffff; color: var(--vacant-font); cursor: pointer; transition: background 0.15s; }
.slot-vacant:hover { background-color: #fef2f2; color: var(--primary-red); }
.slot-occupied {
    background-color: var(--primary-red); color: white; cursor: pointer;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 115px;
    font-weight: bold; padding: 2px 5px; border-radius: 3px; font-size: 10.5px;
}
.slot-paused { background-color: #64748b; color: #cbd5e1; font-style: italic; cursor: not-allowed; }

#sidebar {
    position: fixed; left: -420px; top: 0; width: 380px; height: 100%; max-width: 90vw;
    background: white; box-shadow: 4px 0 20px rgba(0,0,0,0.15);
    transition: left 0.3s ease; z-index: 100; padding: 20px; overflow-y: auto;
}
#sidebar.open { left: 0; }
.drawer-close { font-size: 24px; font-weight: bold; float: right; cursor: pointer; color: #64748b; }
label { font-size: 12px; font-weight: bold; display: block; margin-top: 10px; margin-bottom: 4px; }
input, select, textarea { width: 100%; padding: 8px; border: 1px solid #cbd5e1; border-radius: 4px; font-size: 13px; }

.bottom-portal {
    position: fixed; bottom: 12px; right: 12px; z-index: 40;
    opacity: 0.35; transition: opacity 0.2s; font-size: 11px; background: #ffffff;
    border: 1px solid #cbd5e1; padding: 4px 8px; border-radius: 4px; cursor: pointer;
}
.bottom-portal:hover { opacity: 1.0; }

footer {
    text-align: center; font-size: 12px; color: #64748b; padding: 18px 10px;
    border-top: 1px solid #e2e8f0; background: #ffffff; margin-top: 30px;
}

@media (max-width: 768px) {
    header { padding: 8px 10px; }
    .header-logo { height: 28px; }
    th, td { min-width: 78px; height: 32px; font-size: 10px; }
    th.time-col, td.time-col { min-width: 68px; }
}
"""


# --- MAIN BOOKING GRID ---
@app.get("/", response_class=HTMLResponse)
def index(request: Request, db: Session = Depends(get_db)):
    role = get_current_user_role(request)
    
    groups = db.query(BuildingGroup).order_by(BuildingGroup.display_order, BuildingGroup.id).all()
    all_rooms = (
        db.query(Room)
        .join(BuildingGroup)
        .order_by(BuildingGroup.display_order, Room.display_order, Room.id)
        .all()
    )

    logo_url = get_setting(db, "logo_url", "https://via.placeholder.com/140x40/transparent/dc2626?text=LOGO")
    logo_link = get_setting(db, "logo_link", "https://google.com")
    footer_desc = get_setting(db, "footer_desc", "© 2026 Enterprise Meeting Room System")
    app_title = get_setting(db, "app_title", "Meeting Room Booking Grid")
    btn_book_label = get_setting(db, "btn_book_label", "☰ Book Room")
    btn_dashboard_label = get_setting(db, "btn_dashboard_label", "📊 Today Dashboard")
    btn_manual_label = get_setting(db, "btn_manual_label", "📄 Blank Manual Sheet")
    vacant_label = get_setting(db, "vacant_label", "Vacant")
    drawer_title = get_setting(db, "drawer_title", "Book Meeting Room")

    today = date.today()
    days = [today + timedelta(days=i) for i in range(14)]

    all_bookings = (
        db.query(Booking)
        .filter(Booking.booking_date >= today, Booking.booking_date <= days[-1])
        .all()
    )

    rooms_meta = {
        r.id: {
            "name": r.name,
            "group": r.group.name if r.group else "",
            "facilities": r.facilities or "Standard meeting equipment",
            "image_url": r.image_url or "",
        }
        for r in all_rooms
    }
    rooms_json = json.dumps(rooms_meta)

    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{app_title}</title>
        <style>{BASE_CSS}</style>
    </head>
    <body>
        <header>
            <div class="header-left">
                <a href="{logo_link}" target="_blank">
                    <img src="{logo_url}" class="header-logo" alt="Organization Logo">
                </a>
                <button class="btn" onclick="openDrawer('', '', '')">{btn_book_label}</button>
                <a href="/dashboard" class="btn btn-outline">{btn_dashboard_label}</a>
                <a href="/print-blank-sheet" target="_blank" class="btn btn-outline" style="border-style: dashed;">{btn_manual_label}</a>
                {f'<button class="btn btn-gold" onclick="openTextEditor()">✏️ Edit Viewer Text</button>' if role == "supersuperadmin" else ""}
            </div>
            <div class="header-actions">
                <span>Role: <strong>{role if role else "Viewer"}</strong></span>
                {f'<a href="/admin" style="color: var(--primary-red); font-weight: bold; text-decoration: none;">Admin Panel</a>' if role in ["superadmin", "supersuperadmin"] else ""}
                {f'<a href="/logout" style="color: #64748b; text-decoration: none; margin-left: 6px;">Logout</a>' if role else ''}
            </div>
        </header>

        <!-- Left Drawer -->
        <div id="sidebar">
            <span class="drawer-close" onclick="closeDrawer()">&times;</span>
            <h3 id="drawer-title" style="margin-top: 0; color: var(--primary-red);">{drawer_title}</h3>
            
            <div id="room-info-card" style="background:#fef2f2; border: 1px solid #fecdd3; border-radius: 6px; padding: 10px; margin-top: 8px; font-size: 12px;">
                <img id="room-img" style="width: 100%; height: 120px; object-fit: cover; border-radius: 4px; display: none; margin-bottom: 6px;" src="" alt="Room Photo">
                <div><strong>Facilities:</strong> <span id="room-fac">-</span></div>
            </div>

            <form id="booking-form" action="/book" method="post">
                <input type="hidden" name="booking_id" id="form-booking-id">
                
                <label>Room</label>
                <select name="room_id" id="form-room" onchange="updateRoomPreview(this.value)" required>
                    {"".join([f'<option value="{r.id}">{r.name} ({r.group.name if r.group else ""})</option>' for r in all_rooms if not r.is_paused])}
                </select>

                <label>Date</label>
                <input type="date" name="booking_date" id="form-date" required>

                <label>Start Time</label>
                <select name="start_time" id="form-start-time" required>
                    {"".join([f'<option value="{s[0]}">{s[0]}</option>' for s in SLOTS])}
                </select>

                <label>End Time</label>
                <select name="end_time" id="form-end-time" required>
                    {"".join([f'<option value="{s[1]}">{s[1]}</option>' for s in SLOTS])}
                </select>

                <label>Who is Booking?</label>
                <input type="text" name="booked_by" id="form-booked-by" placeholder="Full name" required>

                <label>Department</label>
                <input type="text" name="department" id="form-department" placeholder="Department" required>

                <label>Agenda</label>
                <textarea name="agenda" id="form-agenda" rows="3" placeholder="Meeting purpose" required></textarea>

                <button type="submit" class="btn" style="width: 100%; margin-top: 14px;">Confirm Reservation</button>
            </form>
            
            <div id="admin-actions" style="display: none; margin-top: 15px; border-top: 1px solid #fee2e2; padding-top: 10px;">
                <form action="/delete-booking" method="post">
                    <input type="hidden" name="booking_id" id="delete-booking-id">
                    <button type="submit" class="btn" style="width: 100%; background: #475569;">Delete Schedule</button>
                </form>
            </div>
        </div>
    """

    date_room_bookings = {}
    for b in all_bookings:
        key = (b.room_id, b.booking_date.isoformat())
        if key not in date_room_bookings:
            date_room_bookings[key] = []
        date_room_bookings[key].append(b)

    for day_idx, current_day in enumerate(days):
        day_str = current_day.isoformat()
        day_label = "Today" if day_idx == 0 else ("Tomorrow" if day_idx == 1 else current_day.strftime("%A"))
        date_heading = f"{day_label} - {current_day.strftime('%B %d, %Y')}"

        html += f"""
        <div class="day-card">
            <div class="day-header">{date_heading}</div>
            <div class="table-wrap">
                <table>
                    <thead>
                        <tr>
                            <th rowspan="2" class="time-col">Time</th>
        """
        for grp in groups:
            r_count = len(grp.rooms)
            if r_count > 0:
                html += f'<th colspan="{r_count}" style="background:#f8fafc; color:#334155;">{grp.name}</th>'

        html += "</tr><tr>"
        for grp in groups:
            for rm in grp.rooms:
                html += f"<th>{rm.name}</th>"
        html += "</tr></thead><tbody>"

        for s_start, s_end in SLOTS:
            slot_start_t = datetime.strptime(s_start, "%H:%M").time()
            html += f'<tr><td class="time-col">{s_start} - {s_end}</td>'

            for grp in groups:
                for rm in grp.rooms:
                    if rm.is_paused:
                        html += '<td class="slot-paused">PAUSED</td>'
                    else:
                        b_list = date_room_bookings.get((rm.id, day_str), [])
                        active_b = None
                        for b in b_list:
                            if b.start_time <= slot_start_t < b.end_time:
                                active_b = b
                                break

                        if active_b:
                            label = f"[{active_b.booked_by}] {active_b.agenda}"
                            payload = f"'{active_b.id}', '{rm.id}', '{day_str}', '{active_b.start_time.strftime('%H:%M')}', '{active_b.end_time.strftime('%H:%M')}', '{active_b.booked_by}', '{active_b.agenda}', '{active_b.department}'"
                            html += f"""<td class="slot-occupied" title="{label}" onclick="openOccupied({payload})">{label}</td>"""
                        else:
                            html += f"""<td class="slot-vacant" onclick="openDrawer('{rm.id}', '{day_str}', '{s_start}')">{vacant_label}</td>"""
            html += "</tr>"
        html += "</tbody></table></div></div>"

    html += f"""
        <button class="bottom-portal" onclick="openLogin()">🔒 Portal</button>

        <div id="login-modal" style="display:none; position:fixed; inset:0; background:rgba(0,0,0,0.5); z-index:200; align-items:center; justify-content:center;">
            <div style="background:white; padding:22px; border-radius:8px; width:300px; border-top: 4px solid var(--primary-red);">
                <h4 style="margin-top:0; color: var(--primary-red);">Staff & Admin Sign In</h4>
                <form action="/login" method="post">
                    <label>Username</label>
                    <input type="text" name="username" required>
                    <label>Password</label>
                    <input type="password" name="password" required>
                    <button type="submit" class="btn" style="width: 100%; margin-top: 14px;">Sign In</button>
                    <button type="button" class="btn" style="background:#94a3b8; width: 100%; margin-top: 6px;" onclick="closeLogin()">Cancel</button>
                </form>
            </div>
        </div>

        <div id="text-editor-modal" style="display:none; position:fixed; inset:0; background:rgba(0,0,0,0.6); z-index:250; align-items:center; justify-content:center; overflow-y:auto; padding:20px;">
            <div style="background:white; padding:24px; border-radius:8px; width:480px; max-width:95vw; border-top: 4px solid #d97706;">
                <h3 style="margin-top:0; color:#d97706;">✏️ SuperSuperAdmin: Live Text Editor</h3>
                <form action="/supersuperadmin/save-texts" method="post">
                    <label>Application Title</label>
                    <input type="text" name="app_title" value="{app_title}" required>

                    <label>Book Button Text</label>
                    <input type="text" name="btn_book_label" value="{btn_book_label}" required>

                    <label>Dashboard Button Text</label>
                    <input type="text" name="btn_dashboard_label" value="{btn_dashboard_label}" required>

                    <label>Blank Manual Sheet Button Text</label>
                    <input type="text" name="btn_manual_label" value="{btn_manual_label}" required>

                    <label>Drawer Header Title</label>
                    <input type="text" name="drawer_title" value="{drawer_title}" required>

                    <label>Vacant Cell Label</label>
                    <input type="text" name="vacant_label" value="{vacant_label}" required>

                    <label>Footer Description</label>
                    <textarea name="footer_desc" rows="2" required>{footer_desc}</textarea>

                    <button type="submit" class="btn btn-gold" style="width: 100%; margin-top: 16px;">Update All Public Viewer Texts</button>
                    <button type="button" class="btn" style="background:#94a3b8; width: 100%; margin-top: 6px;" onclick="closeTextEditor()">Close</button>
                </form>
            </div>
        </div>

        <footer>{footer_desc}</footer>

        <script>
            const userRole = "{role or ''}";
            const roomsData = {rooms_json};

            function updateRoomPreview(roomId) {{
                const r = roomsData[roomId];
                if (!r) return;
                document.getElementById('room-fac').innerText = r.facilities || "Standard room";
                const imgEl = document.getElementById('room-img');
                if (r.image_url && r.image_url.trim() !== "") {{
                    imgEl.src = r.image_url;
                    imgEl.style.display = "block";
                }} else {{
                    imgEl.style.display = "none";
                }}
            }}

            function openDrawer(roomId, dayDate, slotTime) {{
                document.getElementById('form-booking-id').value = "";
                document.getElementById('drawer-title').innerText = "{drawer_title}";
                const roomSelect = document.getElementById('form-room');
                if(roomId) roomSelect.value = roomId;
                updateRoomPreview(roomSelect.value);

                if(dayDate) document.getElementById('form-date').value = dayDate;
                if(slotTime) {{
                    document.getElementById('form-start-time').value = slotTime;
                    const parts = slotTime.split(':');
                    let hr = parseInt(parts[0]);
                    let mn = parseInt(parts[1]) + 30;
                    if(mn >= 60) {{ hr += 1; mn = 0; }}
                    document.getElementById('form-end-time').value = (hr < 10 ? '0'+hr : hr) + ':' + (mn === 0 ? '00' : '30');
                }}
                document.getElementById('admin-actions').style.display = "none";
                document.getElementById('sidebar').classList.add('open');
            }}

            function openOccupied(bId, roomId, bDate, bStart, bEnd, bookedBy, agenda, dept) {{
                // Role Hierarchy: admin, superadmin, and supersuperadmin can all modify bookings
                if (userRole === "admin" || userRole === "superadmin" || userRole === "supersuperadmin") {{
                    document.getElementById('form-booking-id').value = bId;
                    document.getElementById('drawer-title').innerText = "Edit Schedule";
                    document.getElementById('form-room').value = roomId;
                    updateRoomPreview(roomId);
                    document.getElementById('form-date').value = bDate;
                    document.getElementById('form-start-time').value = bStart;
                    document.getElementById('form-end-time').value = bEnd;
                    document.getElementById('form-booked-by').value = bookedBy;
                    document.getElementById('form-department').value = dept;
                    document.getElementById('form-agenda').value = agenda;

                    document.getElementById('delete-booking-id').value = bId;
                    document.getElementById('admin-actions').style.display = "block";
                    document.getElementById('sidebar').classList.add('open');
                }} else {{
                    const r = roomsData[roomId];
                    alert("📌 Meeting Details\\nRoom: " + (r ? r.name : "") + "\\nTime: " + bStart + " - " + bEnd + "\\nBooked By: " + bookedBy + " (" + dept + ")\\nAgenda: " + agenda);
                }}
            }}

            function closeDrawer() {{ document.getElementById('sidebar').classList.remove('open'); }}
            function openLogin() {{ document.getElementById('login-modal').style.display = "flex"; }}
            function closeLogin() {{ document.getElementById('login-modal').style.display = "none"; }}
            function openTextEditor() {{ document.getElementById('text-editor-modal').style.display = "flex"; }}
            function closeTextEditor() {{ document.getElementById('text-editor-modal').style.display = "none"; }}

            const initRoom = document.getElementById('form-room');
            if (initRoom && initRoom.value) updateRoomPreview(initRoom.value);
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html)


# --- LIVE WEB DASHBOARD ---
@app.get("/dashboard", response_class=HTMLResponse)
def today_dashboard(db: Session = Depends(get_db)):
    logo_url = get_setting(db, "logo_url", "")
    logo_link = get_setting(db, "logo_link", "#")
    today = date.today()
    now_time = datetime.now().time()

    today_bookings = (
        db.query(Booking)
        .filter(Booking.booking_date == today)
        .order_by(Booking.start_time)
        .all()
    )

    total_rooms = db.query(Room).count()
    active_now = sum(1 for b in today_bookings if b.start_time <= now_time <= b.end_time)

    dash_html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <meta http-equiv="refresh" content="300">
        <title>Today Dashboard - {today.isoformat()}</title>
        <style>
            {BASE_CSS}
            .dash-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 14px; margin-bottom: 20px; }}
            .metric-card {{ background: white; padding: 16px; border-radius: 8px; border-left: 4px solid var(--primary-red); box-shadow: 0 1px 3px rgba(0,0,0,0.05); }}
            .metric-val {{ font-size: 24px; font-weight: bold; color: var(--primary-red); margin-top: 4px; }}
            
            @media print {{
                @page {{ size: A4 portrait; margin: 10mm; }}
                body {{ background: white !important; color: black !important; padding: 0 !important; }}
                .no-print, header, .btn, footer, .bottom-portal {{ display: none !important; }}
                .dash-grid {{ display: flex !important; gap: 10px; margin-bottom: 12px; }}
                .metric-card {{ border: 1px solid #ccc !important; border-left: 4px solid #000 !important; box-shadow: none !important; padding: 8px !important; flex: 1; }}
                .metric-val {{ font-size: 18px !important; color: black !important; }}
                table {{ font-size: 10px !important; width: 100% !important; }}
                th, td {{ padding: 5px !important; border: 1px solid #666 !important; height: auto !important; }}
                th {{ background: #eee !important; color: black !important; }}
                .print-header {{ display: block !important; margin-bottom: 14px; border-bottom: 2px solid #000; padding-bottom: 8px; }}
            }}
            .print-header {{ display: none; }}
        </style>
    </head>
    <body style="padding: 16px; max-width: 1050px; margin: auto;">
        <header class="no-print" style="border-radius: 8px; margin-bottom: 20px;">
            <div class="header-left">
                <a href="{logo_link}"><img src="{logo_url}" class="header-logo"></a>
                <span style="font-size: 1.1rem; font-weight: bold; color: #1e293b;">Live Meeting Dashboard</span>
            </div>
            <div class="header-actions">
                <button onclick="window.print()" class="btn">🖨️ Print to A4</button>
                <a href="/" class="btn btn-outline">&larr; Back to Grid</a>
            </div>
        </header>

        <div class="print-header">
            <h2 style="margin: 0; font-size: 18px; text-transform: uppercase;">Official Meeting Schedule Report</h2>
            <div style="font-size: 12px; color: #444; margin-top: 4px;">
                Date: <strong>{today.strftime('%A, %B %d, %Y')}</strong> • Generated: {datetime.now().strftime('%H:%M')}
            </div>
        </div>

        <div class="no-print" style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
            <h3 style="margin: 0;">Today's Schedule ({today.strftime('%A, %B %d, %Y')})</h3>
            <span style="font-size: 12px; color: #64748b;">⏱ Auto-refreshes every 5 mins</span>
        </div>

        <div class="dash-grid">
            <div class="metric-card"><div>Total Meetings Today</div><div class="metric-val">{len(today_bookings)}</div></div>
            <div class="metric-card"><div>In-Progress Now</div><div class="metric-val">{active_now}</div></div>
            <div class="metric-card"><div>Total Managed Rooms</div><div class="metric-val">{total_rooms}</div></div>
        </div>

        <div class="day-card" style="width: 100%; margin: 0; box-shadow: none;">
            <div class="table-wrap">
                <table>
                    <thead>
                        <tr style="background: #f8fafc;">
                            <th>Time</th><th>Room</th><th>Building</th><th>Booked By</th><th>Department</th><th>Agenda</th><th>Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        {"".join([f'''<tr>
                            <td><strong>{b.start_time.strftime('%H:%M')} - {b.end_time.strftime('%H:%M')}</strong></td>
                            <td><strong>{b.room.name}</strong></td>
                            <td>{b.room.group.name if b.room.group else "-"}</td>
                            <td>{b.booked_by}</td>
                            <td>{b.department}</td>
                            <td>{b.agenda}</td>
                            <td>{'<strong style="color:var(--primary-red);">IN PROGRESS</strong>' if b.start_time <= now_time <= b.end_time else ('UPCOMING' if b.start_time > now_time else 'COMPLETED')}</td>
                        </tr>''' for b in today_bookings]) if today_bookings else '<tr><td colspan="7" style="padding: 24px;">No meetings scheduled for today yet.</td></tr>'}
                    </tbody>
                </table>
            </div>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=dash_html)


# --- EMERGENCY OFFLINE PRINT SHEET ---
@app.get("/print-blank-sheet", response_class=HTMLResponse)
def print_blank_sheet(db: Session = Depends(get_db)):
    all_rooms = (
        db.query(Room)
        .join(BuildingGroup)
        .order_by(BuildingGroup.display_order, Room.display_order, Room.id)
        .all()
    )
    footer_desc = get_setting(db, "footer_desc", "Enterprise Meeting Room Reservation")

    blank_html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Blank Offline Room Reservation Sheet</title>
        <style>
            * {{ box-sizing: border-box; font-family: Arial, Helvetica, sans-serif !important; }}
            @page {{ size: A4 landscape; margin: 8mm; }}
            body {{ margin: 0; background: white; color: #000; font-size: 10px; }}
            .print-bar {{
                background: #f1f5f9; padding: 10px 14px; margin-bottom: 12px;
                display: flex; justify-content: space-between; align-items: center;
                border: 1px solid #cbd5e1; border-radius: 6px;
            }}
            .btn-print {{ background: #dc2626; color: white; border: none; padding: 8px 18px; border-radius: 4px; font-weight: bold; cursor: pointer; }}
            .sheet-title {{ display: flex; justify-content: space-between; align-items: flex-end; border-bottom: 2px solid #000; padding-bottom: 6px; margin-bottom: 8px; }}
            table {{ width: 100%; border-collapse: collapse; table-layout: fixed; }}
            th, td {{ border: 1px solid #333; padding: 3px 2px; text-align: center; height: 26px; }}
            th {{ background: #f3f4f6; font-size: 9px; }}
            .time-col {{ width: 68px; font-weight: bold; background: #fafafa; font-size: 9px; }}
            @media print {{
                .print-bar {{ display: none !important; }}
                th {{ background: #e5e7eb !important; -webkit-print-color-adjust: exact; }}
            }}
        </style>
    </head>
    <body>
        <div class="print-bar">
            <div><strong>Emergency Manual Booking Form (Offline Backup)</strong> — Print this paper sheet when web/power is unavailable.</div>
            <button class="btn-print" onclick="window.print()">🖨️ Print Blank A4 Sheet</button>
        </div>

        <div class="sheet-title">
            <div>
                <h2 style="margin: 0; font-size: 16px; text-transform: uppercase;">Manual Meeting Room Schedule</h2>
                <span style="font-size: 11px;">Building & Facilities Emergency Operations Log</span>
            </div>
            <div style="font-size: 11px; text-align: right;">
                Date: ________________________ &nbsp;&nbsp;|&nbsp;&nbsp; Supervisor Sign: ________________________
            </div>
        </div>

        <table>
            <thead>
                <tr>
                    <th class="time-col">Time Slot</th>
                    {"".join([f'<th><div><strong>{r.name}</strong></div><div style="font-size:7.5px;color:#555;">{r.group.name if r.group else ""}</div></th>' for r in all_rooms])}
                </tr>
            </thead>
            <tbody>
                {"".join([f'''<tr>
                    <td class="time-col">{s[0]} - {s[1]}</td>
                    {"".join(['<td></td>' for _ in all_rooms])}
                </tr>''' for s in SLOTS])}
            </tbody>
        </table>

        <div style="margin-top: 10px; display: flex; justify-content: space-between; font-size: 9px; color: #555;">
            <div>Instructions: Write [Organizer Name] [Department] [Agenda] clearly in ink.</div>
            <div>{footer_desc}</div>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=blank_html)


# --- ADMIN & SUPERSUPERADMIN PANEL ---
@app.get("/admin", response_class=HTMLResponse)
def admin_panel(request: Request, db: Session = Depends(get_db)):
    role = get_current_user_role(request)
    # Role Hierarchy: Only superadmin and supersuperadmin can access this panel
    if role not in ["superadmin", "supersuperadmin"]:
        return RedirectResponse(url="/", status_code=303)

    groups = db.query(BuildingGroup).order_by(BuildingGroup.display_order, BuildingGroup.id).all()
    rooms = (
        db.query(Room)
        .join(BuildingGroup)
        .order_by(BuildingGroup.display_order, Room.display_order, Room.id)
        .all()
    )

    logo_url = get_setting(db, "logo_url")
    logo_link = get_setting(db, "logo_link")
    footer_desc = get_setting(db, "footer_desc")

    admin_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Admin & Room Sorting Panel</title>
        <style>
            {BASE_CSS}
            body {{ padding: 20px; max-width: 1050px; margin: auto; }}
            .card {{ background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; border: 1px solid #e2e8f0; }}
            input, select, textarea {{ margin-top: 4px; }}
        </style>
    </head>
    <body>
        <p><a href="/" class="btn btn-outline" style="font-size: 12px;">&larr; Back to Booking Grid</a></p>
        <h2 style="color: var(--primary-red);">Administration & Manual Room Sorting Panel</h2>
        <p style="font-size: 13px; color: #64748b;">Active Role: <strong>{role}</strong></p>

        <!-- RESTORED: Logo, Link, and Footer Branding Configuration -->
        <div class="card">
            <h3>🎨 Branding & Header/Footer Settings</h3>
            <form action="/admin/save-settings" method="post" style="display: flex; flex-direction: column; gap: 10px;">
                <div>
                    <label>Header Logo (Transparent PNG URL)</label>
                    <input type="text" name="logo_url" value="{logo_url}" required>
                </div>
                <div>
                    <label>Logo Click Destination Webpage</label>
                    <input type="text" name="logo_link" value="{logo_link}" required>
                </div>
                <div>
                    <label>Footer Description Text</label>
                    <input type="text" name="footer_desc" value="{footer_desc}" required>
                </div>
                <button type="submit" class="btn" style="align-self: flex-start;">Save Branding & Footer</button>
            </form>
        </div>

        <!-- Manage Building Groups -->
        <div class="card">
            <h3>🏢 Manage Building Groups & Manual Order</h3>
            <form action="/admin/add-group" method="post" style="display: flex; gap: 8px; margin-bottom: 14px;">
                <input type="text" name="name" placeholder="New Building Name (e.g. Tower North)" required>
                <input type="number" name="display_order" placeholder="Order (1, 2, 3...)" style="width: 160px;" value="{len(groups)+1}">
                <button type="submit" class="btn">Create Group</button>
            </form>

            <div class="table-wrap">
                <table>
                    <tr style="background:#f8fafc;"><th>Building Name</th><th>Sort Order Priority</th><th>Actions</th></tr>
                    {"".join([f'''<tr>
                        <form action="/admin/update-group/{g.id}" method="post">
                            <td><input type="text" name="name" value="{g.name}" required></td>
                            <td style="width: 120px;"><input type="number" name="display_order" value="{g.display_order}" required></td>
                            <td style="width: 140px;">
                                <button type="submit" class="btn" style="padding: 4px 10px; font-size: 11px;">Save Order</button>
                                <a href="/admin/delete-group/{g.id}" onclick="return confirm('Delete {g.name} and all its rooms?');" style="color:var(--primary-red); margin-left: 8px; font-size: 11px;">Delete</a>
                            </td>
                        </form>
                    </tr>''' for g in groups])}
                </table>
            </div>
        </div>

        <!-- Add Room -->
        <div class="card">
            <h3>Add New Room</h3>
            <form action="/admin/add-room" method="post" style="display: flex; flex-direction: column; gap: 10px;">
                <div style="display: flex; gap: 10px;">
                    <input type="text" name="name" placeholder="Room Name" required>
                    <select name="group_id">
                        {"".join([f'<option value="{g.id}">{g.name}</option>' for g in groups])}
                    </select>
                    <input type="number" name="display_order" placeholder="Order (e.g. 1)" style="width: 120px;" value="1">
                </div>
                <input type="text" name="image_url" placeholder="Image URL (transparent PNG / photo)">
                <input type="text" name="facilities" placeholder="Facilities (e.g. Projector, Mic, 16 Chairs)">
                <button type="submit" class="btn" style="align-self: flex-start;">Create Room</button>
            </form>
        </div>

        <!-- Manage Rooms & Ordering -->
        <div class="card">
            <h3>📋 Manage Rooms & Left-to-Right Sort Priority</h3>
            <p style="font-size: 12px; color: #64748b;">Lower numbers render first (left-to-right) within their building group.</p>
            <div class="table-wrap">
                <table>
                    <tr style="background: #f8fafc;">
                        <th>Room</th><th>Building</th><th>Sort Order</th><th>Facilities</th><th>Image</th><th>Status</th><th>Actions</th>
                    </tr>
                    {"".join([f'''<tr>
                        <form action="/admin/update-room/{r.id}" method="post">
                            <td><input type="text" name="name" value="{r.name}" style="width: 95px;" required></td>
                            <td>
                                <select name="group_id" style="width: 105px;">
                                    {"".join([f'<option value="{g.id}" {"selected" if g.id == r.group_id else ""}>{g.name}</option>' for g in groups])}
                                </select>
                            </td>
                            <td style="width: 75px;"><input type="number" name="display_order" value="{r.display_order}" required></td>
                            <td><input type="text" name="facilities" value="{r.facilities or ''}"></td>
                            <td><input type="text" name="image_url" value="{r.image_url or ''}"></td>
                            <td><strong>{"PAUSED" if r.is_paused else "ACTIVE"}</strong></td>
                            <td style="white-space: nowrap;">
                                <button type="submit" class="btn" style="padding: 4px 8px; font-size: 11px;">Save</button>
                                <a href="/admin/toggle-room/{r.id}" style="margin-left: 6px; font-size: 11px;">{"Resume" if r.is_paused else "Pause"}</a>
                                <a href="/admin/delete-room/{r.id}" onclick="return confirm('Delete {r.name}?');" style="margin-left: 6px; color: var(--primary-red); font-size: 11px;">Delete</a>
                            </td>
                        </form>
                    </tr>''' for r in rooms])}
                </table>
            </div>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=admin_html)


# --- AUTH & ACTIONS WITH CASCADING ROLE HIERARCHY ---
@app.post("/login")
def login(username: str = Form(...), password: str = Form(...)):
    role = None
    if username == "supersuperadmin" and password == "supersuperadmin":
        role = "supersuperadmin"
    elif username == "superadmin" and password == "superadmin":
        role = "superadmin"
    elif username == "admin" and password == "admin":
        role = "admin"

    if role:
        response = RedirectResponse(url="/", status_code=303)
        response.set_cookie(key="user_role", value=role, httponly=True)
        return response
    return HTMLResponse("<script>alert('Invalid credentials'); window.location.href='/';</script>")


@app.get("/logout")
def logout():
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie("user_role")
    return response


# Branding Settings (superadmin & supersuperadmin)
@app.post("/admin/save-settings")
def save_settings(
    logo_url: str = Form(...),
    logo_link: str = Form(...),
    footer_desc: str = Form(...),
    request: Request = None,
    db: Session = Depends(get_db),
):
    if get_current_user_role(request) in ["superadmin", "supersuperadmin"]:
        set_setting(db, "logo_url", logo_url)
        set_setting(db, "logo_link", logo_link)
        set_setting(db, "footer_desc", footer_desc)
    return RedirectResponse(url="/admin", status_code=303)


# Public Text Editor (supersuperadmin only)
@app.post("/supersuperadmin/save-texts")
def save_texts(
    app_title: str = Form(...),
    btn_book_label: str = Form(...),
    btn_dashboard_label: str = Form(...),
    btn_manual_label: str = Form(...),
    drawer_title: str = Form(...),
    vacant_label: str = Form(...),
    footer_desc: str = Form(...),
    request: Request = None,
    db: Session = Depends(get_db),
):
    if get_current_user_role(request) == "supersuperadmin":
        set_setting(db, "app_title", app_title)
        set_setting(db, "btn_book_label", btn_book_label)
        set_setting(db, "btn_dashboard_label", btn_dashboard_label)
        set_setting(db, "btn_manual_label", btn_manual_label)
        set_setting(db, "drawer_title", drawer_title)
        set_setting(db, "vacant_label", vacant_label)
        set_setting(db, "footer_desc", footer_desc)
    return RedirectResponse(url="/", status_code=303)


# Building Groups Management (superadmin & supersuperadmin)
@app.post("/admin/add-group")
def add_group(name: str = Form(...), display_order: int = Form(0), request: Request = None, db: Session = Depends(get_db)):
    if get_current_user_role(request) in ["superadmin", "supersuperadmin"]:
        db.add(BuildingGroup(name=name, display_order=display_order))
        db.commit()
    return RedirectResponse(url="/admin", status_code=303)


@app.post("/admin/update-group/{group_id}")
def update_group(group_id: int, name: str = Form(...), display_order: int = Form(0), request: Request = None, db: Session = Depends(get_db)):
    if get_current_user_role(request) in ["superadmin", "supersuperadmin"]:
        g = db.query(BuildingGroup).filter(BuildingGroup.id == group_id).first()
        if g:
            g.name = name
            g.display_order = display_order
            db.commit()
    return RedirectResponse(url="/admin", status_code=303)


@app.get("/admin/delete-group/{group_id}")
def delete_group(group_id: int, request: Request = None, db: Session = Depends(get_db)):
    if get_current_user_role(request) in ["superadmin", "supersuperadmin"]:
        g = db.query(BuildingGroup).filter(BuildingGroup.id == group_id).first()
        if g:
            db.delete(g)
            db.commit()
    return RedirectResponse(url="/admin", status_code=303)


# Room Management (superadmin & supersuperadmin)
@app.post("/admin/add-room")
def add_room(
    name: str = Form(...),
    group_id: int = Form(...),
    display_order: int = Form(0),
    image_url: Optional[str] = Form(""),
    facilities: Optional[str] = Form(""),
    request: Request = None,
    db: Session = Depends(get_db),
):
    if get_current_user_role(request) in ["superadmin", "supersuperadmin"]:
        db.add(Room(name=name, group_id=group_id, display_order=display_order, image_url=image_url, facilities=facilities))
        db.commit()
    return RedirectResponse(url="/admin", status_code=303)


@app.post("/admin/update-room/{room_id}")
def update_room(
    room_id: int,
    name: str = Form(...),
    group_id: int = Form(...),
    display_order: int = Form(0),
    image_url: Optional[str] = Form(""),
    facilities: Optional[str] = Form(""),
    request: Request = None,
    db: Session = Depends(get_db),
):
    if get_current_user_role(request) in ["superadmin", "supersuperadmin"]:
        rm = db.query(Room).filter(Room.id == room_id).first()
        if rm:
            rm.name = name
            rm.group_id = group_id
            rm.display_order = display_order
            rm.image_url = image_url
            rm.facilities = facilities
            db.commit()
    return RedirectResponse(url="/admin", status_code=303)


@app.get("/admin/delete-room/{room_id}")
def delete_room(room_id: int, request: Request = None, db: Session = Depends(get_db)):
    if get_current_user_role(request) in ["superadmin", "supersuperadmin"]:
        rm = db.query(Room).filter(Room.id == room_id).first()
        if rm:
            db.delete(rm)
            db.commit()
    return RedirectResponse(url="/admin", status_code=303)


@app.get("/admin/toggle-room/{room_id}")
def toggle_room(room_id: int, request: Request = None, db: Session = Depends(get_db)):
    if get_current_user_role(request) in ["superadmin", "supersuperadmin"]:
        rm = db.query(Room).filter(Room.id == room_id).first()
        if rm:
            rm.is_paused = not rm.is_paused
            db.commit()
    return RedirectResponse(url="/admin", status_code=303)


# Booking Save & Overdrive (All admin roles inherit access)
@app.post("/book")
def save_booking(
    booking_id: Optional[str] = Form(None),
    room_id: int = Form(...),
    booking_date: str = Form(...),
    start_time: str = Form(...),
    end_time: str = Form(...),
    booked_by: str = Form(...),
    agenda: str = Form(...),
    department: str = Form(...),
    request: Request = None,
    db: Session = Depends(get_db),
):
    role = get_current_user_role(request)
    b_date = datetime.strptime(booking_date, "%Y-%m-%d").date()
    s_time = datetime.strptime(start_time, "%H:%M").time()
    e_time = datetime.strptime(end_time, "%H:%M").time()

    if s_time >= e_time:
        return HTMLResponse("<script>alert('End time must be after start time.'); window.history.back();</script>")

    # Edit existing booking (admin, superadmin, and supersuperadmin can modify)
    if booking_id and booking_id.strip():
        existing = db.query(Booking).filter(Booking.id == int(booking_id)).first()
        if existing and role in ["admin", "superadmin", "supersuperadmin"]:
            existing.room_id = room_id
            existing.booking_date = b_date
            existing.start_time = s_time
            existing.end_time = e_time
            existing.booked_by = booked_by
            existing.agenda = agenda
            existing.department = department
            db.commit()
            return RedirectResponse(url="/", status_code=303)

    # Overdrive permissions: superadmin & supersuperadmin can overdrive conflicts
    if role not in ["superadmin", "supersuperadmin"]:
        overlap = (
            db.query(Booking)
            .filter(
                Booking.room_id == room_id,
                Booking.booking_date == b_date,
                Booking.start_time < e_time,
                Booking.end_time > s_time,
            )
            .first()
        )
        if overlap:
            return HTMLResponse("<script>alert('One or more selected slots are already occupied!'); window.history.back();</script>")

    new_book = Booking(
        room_id=room_id,
        booking_date=b_date,
        start_time=s_time,
        end_time=e_time,
        booked_by=booked_by,
        agenda=agenda,
        department=department,
    )
    db.add(new_book)
    db.commit()
    return RedirectResponse(url="/", status_code=303)


# Booking Delete (admin, superadmin, and supersuperadmin can delete)
@app.post("/delete-booking")
def delete_booking(booking_id: int = Form(...), request: Request = None, db: Session = Depends(get_db)):
    role = get_current_user_role(request)
    if role in ["admin", "superadmin", "supersuperadmin"]:
        b = db.query(Booking).filter(Booking.id == booking_id).first()
        if b:
            db.delete(b)
            db.commit()
    return RedirectResponse(url="/", status_code=303)


if __name__ == "__main__":
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)