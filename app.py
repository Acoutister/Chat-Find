from flask import Flask, render_template, request, redirect, url_for, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta, timezone
from functools import wraps
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['SECRET_KEY'] = 'feibo_yuqing_123'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'uploads')
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif', 'mp3', 'wav', 'ogg', 'webm', 'pdf', 'doc', 'docx',
                                    'txt', 'zip'}
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

db = SQLAlchemy(app)


# ==========================================
# 权限拦截器
# ==========================================

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        user = db.session.get(User, session['user_id'])
        if not user:
            session.clear()
            return redirect(url_for('login'))
        return f(*args, **kwargs)

    return decorated_function


def local_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.remote_addr not in ['127.0.0.1', '::1']:
            return "Access Denied: Only localhost can access this page.", 403
        return f(*args, **kwargs)

    return decorated_function


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


def get_file_type(filename):
    ext = filename.rsplit('.', 1)[1].lower()
    if ext in {'png', 'jpg', 'jpeg', 'gif'}:
        return 'image'
    elif ext in {'mp3', 'wav', 'ogg', 'webm'}:
        return 'audio'
    else:
        return 'file'


def now_utc():
    return datetime.now(timezone.utc)


# ==========================================
# 数据库模型
# ==========================================

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)
    nickname = db.Column(db.String(50), nullable=True)
    is_online = db.Column(db.Boolean, default=False)
    last_active = db.Column(db.DateTime, default=now_utc)
    avatar = db.Column(db.String(200), nullable=True)
    gender = db.Column(db.String(10), nullable=True)
    province = db.Column(db.String(20), nullable=True)
    is_matching = db.Column(db.Boolean, default=False)
    matched_with_id = db.Column(db.Integer, nullable=True)
    is_admin = db.Column(db.Boolean, default=False)


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.String(500), nullable=True)
    date_posted = db.Column(db.DateTime, default=now_utc)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    file_type = db.Column(db.String(20), nullable=True)
    file_path = db.Column(db.String(200), nullable=True)
    file_name = db.Column(db.String(200), nullable=True)
    is_read = db.Column(db.Boolean, default=False)
    is_deleted = db.Column(db.Boolean, default=False)


class Moment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=True)
    image_path = db.Column(db.String(200), nullable=True)
    date_posted = db.Column(db.DateTime, default=now_utc)
    likes = db.Column(db.Integer, default=0)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)


class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    moment_id = db.Column(db.Integer, db.ForeignKey('moment.id'), nullable=False)


class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.String(300), nullable=False)
    date_posted = db.Column(db.DateTime, default=now_utc)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    moment_id = db.Column(db.Integer, db.ForeignKey('moment.id'), nullable=False)


class Favorite(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    moment_id = db.Column(db.Integer, db.ForeignKey('moment.id'), nullable=False)
    date_favorited = db.Column(db.DateTime, default=now_utc)


class Friendship(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    friend_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=now_utc)


class InvitationCode(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    is_used = db.Column(db.Boolean, default=False)
    used_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=now_utc)


with app.app_context():
    db.create_all()


# ==========================================
# 本地专属：后端管理页面与接口
# ==========================================

@app.route('/admin')
@local_only
def admin_panel():
    return render_template('admin.html')


@app.route('/api/admin/stats')
@local_only
def admin_stats():
    online_count = User.query.filter_by(is_online=True).count()
    total_users = User.query.count()
    total_moments = Moment.query.count()
    return jsonify({"online_count": online_count, "total_users": total_users, "total_moments": total_moments})


@app.route('/api/admin/users')
@local_only
def admin_users():
    users = User.query.all()
    res = [
        {"id": u.id, "username": u.username, "nickname": u.nickname, "is_admin": u.is_admin, "is_online": u.is_online}
        for u in users]
    return jsonify(res)


@app.route('/api/admin/toggle_admin/<int:user_id>', methods=['POST'])
@local_only
def toggle_admin(user_id):
    user = db.session.get(User, user_id)
    if user:
        user.is_admin = not user.is_admin
        db.session.commit()
        return jsonify({"ok": 1, "is_admin": user.is_admin})
    return jsonify({"ok": 0}), 404


# ==========================================
# 基础页面与认证路由
# ==========================================

@app.route('/')
def home():
    return redirect(url_for('login'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        invite_code = request.form.get('invitation_code')

        if not invite_code: return render_template('register.html', error="注册需要邀请码")
        inv_record = InvitationCode.query.filter_by(code=invite_code, is_used=False).first()
        if not inv_record: return render_template('register.html', error="邀请码无效或已被使用")
        if User.query.filter_by(username=username).first(): return render_template('register.html',
                                                                                   error="该账号已被注册")

        hashed = generate_password_hash(password)
        new_user = User(username=username, password=hashed, nickname=username)
        if User.query.count() == 0: new_user.is_admin = True

        db.session.add(new_user)
        db.session.commit()

        inv_record.is_used = True
        inv_record.used_by_id = new_user.id
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and check_password_hash(user.password, request.form['password']):
            session['user_id'] = user.id
            session['username'] = user.username
            user.is_online = True
            user.last_active = now_utc()
            db.session.commit()
            return redirect(url_for('chat'))
        else:
            return render_template('login.html', error="用户名或密码错误")
    return render_template('login.html')


@app.route('/logout')
def logout():
    if 'user_id' in session:
        user = db.session.get(User, session['user_id'])
        if user:
            user.is_online = False
            user.is_matching = False
            db.session.commit()
    session.clear()
    return redirect(url_for('login'))


@app.route('/chat')
@login_required
def chat():
    user = db.session.get(User, session['user_id'])
    return render_template('chat.html', username=user.username, nickname=user.nickname, avatar=user.avatar,
                           is_admin=str(user.is_admin))


# ==========================================
# 系统状态与个人设置 API
# ==========================================

@app.route('/api/heartbeat')
@login_required
def heartbeat():
    user = db.session.get(User, session['user_id'])
    if user:
        user.is_online = True
        user.last_active = now_utc()
        db.session.commit()
    timeout = now_utc() - timedelta(minutes=2)
    User.query.filter(User.last_active < timeout).update({User.is_online: False})
    db.session.commit()
    return jsonify({"ok": 1})


@app.route('/api/upload_avatar', methods=['POST'])
@login_required
def upload_avatar():
    file = request.files.get('avatar')
    if file and allowed_file(file.filename) and get_file_type(file.filename) == 'image':
        fname = secure_filename(file.filename)
        save_name = f"avatar_{session['user_id']}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{fname}"
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], save_name))
        user = db.session.get(User, session['user_id'])
        user.avatar = save_name
        db.session.commit()
        return jsonify({"ok": 1, "avatar": save_name})
    return jsonify({"ok": 0, "error": "无效的图片格式"})


@app.route('/api/update_nickname', methods=['POST'])
@login_required
def update_nickname():
    new_name = request.form.get('nickname')
    if new_name and len(new_name.strip()) > 0:
        user = db.session.get(User, session['user_id'])
        user.nickname = new_name.strip()
        db.session.commit()
        return jsonify({"ok": 1})
    return jsonify({"ok": 0})


# ==========================================
# 好友系统 API
# ==========================================

@app.route('/api/contacts')
@login_required
def contacts():
    uid = session['user_id']
    friendships = Friendship.query.filter(
        ((Friendship.user_id == uid) | (Friendship.friend_id == uid)) & (Friendship.status == 'accepted')
    ).all()

    friends_data = []
    for f in friendships:
        fid = f.friend_id if f.user_id == uid else f.user_id
        u = db.session.get(User, fid)
        if u:
            unread = Message.query.filter_by(user_id=fid, receiver_id=uid, is_read=False, is_deleted=False).count()
            friends_data.append(
                {"id": u.id, "username": u.nickname, "avatar": u.avatar, "is_online": u.is_online, "unread": unread})
    return jsonify(friends_data)


@app.route('/api/friend_requests', methods=['GET'])
@login_required
def friend_requests():
    uid = session['user_id']
    requests = Friendship.query.filter_by(friend_id=uid, status='pending').all()
    res = [{"id": r.id, "requester_id": db.session.get(User, r.user_id).id,
            "username": db.session.get(User, r.user_id).nickname, "avatar": db.session.get(User, r.user_id).avatar} for
           r in requests if db.session.get(User, r.user_id)]
    return jsonify(res)


@app.route('/api/add_friend/<int:target_id>', methods=['POST'])
@login_required
def add_friend(target_id):
    uid = session['user_id']
    exist = Friendship.query.filter(((Friendship.user_id == uid) & (Friendship.friend_id == target_id)) | (
                (Friendship.user_id == target_id) & (Friendship.friend_id == uid))).first()
    if not exist:
        db.session.add(Friendship(user_id=uid, friend_id=target_id))
        db.session.commit()
    return jsonify({"ok": 1})


@app.route('/api/accept_friend/<int:req_id>', methods=['POST'])
@login_required
def accept_friend(req_id):
    req = db.session.get(Friendship, req_id)
    if req and req.friend_id == session['user_id']:
        req.status = 'accepted'
        db.session.add(
            Message(user_id=session['user_id'], receiver_id=req.user_id, content="我们已经是好友啦，开始聊天吧！"))
        db.session.commit()
        return jsonify({"ok": 1})
    return jsonify({"ok": 0})


# ==========================================
# 消息收发与同步 API
# ==========================================

@app.route('/api/send', methods=['POST'])
@login_required
def send():
    msg = Message(user_id=session['user_id'], receiver_id=request.form.get('receiver_id', type=int),
                  content=request.form.get('content', ''))
    file = request.files.get('file')
    if file and allowed_file(file.filename):
        fname = secure_filename(file.filename)
        save_name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{fname}"
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], save_name))
        msg.file_type, msg.file_path, msg.file_name = get_file_type(fname), save_name, fname
    db.session.add(msg)
    db.session.commit()
    return jsonify({"ok": 1})


@app.route('/api/public-messages')
@login_required
def public_messages():
    last_id = request.args.get('last_id', 0, type=int)
    msgs = Message.query.filter(Message.id > last_id, Message.receiver_id == None).order_by(
        Message.date_posted.asc()).all()
    res = []
    for m in msgs:
        u = db.session.get(User, m.user_id)
        # 本地化时间给前端展示
        local_time = m.date_posted.replace(tzinfo=timezone.utc).astimezone(tz=None)
        res.append(
            {"id": m.id, "sender_id": m.user_id, "user": u.nickname if u else "?", "avatar": u.avatar if u else None,
             "is_admin": u.is_admin if u else False, "content": m.content, "time": local_time.strftime('%H:%M'),
             "file_type": m.file_type, "file_path": m.file_path, "file_name": m.file_name, "is_deleted": m.is_deleted})
    return jsonify(res)


@app.route('/api/private-messages')
@login_required
def private_messages():
    last_id = request.args.get('last_id', 0, type=int)
    with_uid = request.args.get('with', type=int)
    uid = session['user_id']

    msgs = Message.query.filter(
        Message.id > last_id,
        (((Message.user_id == uid) & (Message.receiver_id == with_uid)) |
         ((Message.user_id == with_uid) & (Message.receiver_id == uid)))
    ).order_by(Message.date_posted.asc()).all()

    unread_msgs = [m for m in msgs if m.receiver_id == uid and not m.is_read and not m.is_deleted]
    if unread_msgs:
        for m in unread_msgs: m.is_read = True
        db.session.commit()

    res = []
    for m in msgs:
        u = db.session.get(User, m.user_id)
        local_time = m.date_posted.replace(tzinfo=timezone.utc).astimezone(tz=None)
        res.append(
            {"id": m.id, "sender_id": m.user_id, "user": u.nickname if u else "?", "avatar": u.avatar if u else None,
             "is_admin": u.is_admin if u else False, "content": m.content, "time": local_time.strftime('%H:%M'),
             "file_type": m.file_type, "file_path": m.file_path, "file_name": m.file_name, "is_deleted": m.is_deleted})
    return jsonify(res)


@app.route('/api/messages/<int:msg_id>', methods=['DELETE'])
@login_required
def delete_message(msg_id):
    uid = session['user_id']
    user = db.session.get(User, uid)
    m = db.session.get(Message, msg_id)
    if m and (m.user_id == uid or user.is_admin):
        m.is_deleted = True
        db.session.commit()
        return jsonify({"ok": 1})
    return jsonify({"ok": 0, "error": "无权限或消息不存在"}), 403


@app.route('/api/deleted_messages')
@login_required
def get_deleted_messages():
    deleted_msgs = Message.query.filter_by(is_deleted=True).all()
    return jsonify([m.id for m in deleted_msgs])


# ==========================================
# 灵魂匹配 API
# ==========================================

@app.route('/api/start_match', methods=['POST'])
@login_required
def start_match():
    uid = session['user_id']
    user = db.session.get(User, uid)
    data = request.json
    user.gender, user.province, preference = data.get('gender'), data.get('province'), data.get('preference')
    user.is_matching, user.matched_with_id = True, None
    db.session.commit()

    query = User.query.filter(User.is_matching == True, User.id != uid)
    if preference == 'same_province':
        query = query.filter(User.province == user.province)
    elif preference == 'same_gender':
        query = query.filter(User.gender == user.gender)
    elif preference == 'diff_gender':
        query = query.filter(User.gender == ('女' if user.gender == '男' else '男'))

    target = query.first()
    if target:
        user.is_matching, target.is_matching = False, False
        user.matched_with_id, target.matched_with_id = target.id, user.id
        db.session.add(
            Message(user_id=target.id, receiver_id=user.id, content="✨ 灵魂匹配成功！我在这里，快来打个招呼吧~"))
        db.session.commit()
        return jsonify(
            {"status": "success", "peer_id": target.id, "peer_name": target.nickname, "peer_avatar": target.avatar})
    return jsonify({"status": "searching"})


@app.route('/api/check_match_status')
@login_required
def check_match_status():
    user = db.session.get(User, session['user_id'])
    if not user.is_matching and user.matched_with_id:
        peer = db.session.get(User, user.matched_with_id)
        if peer: return jsonify(
            {"status": "matched", "peer_id": peer.id, "peer_name": peer.nickname, "peer_avatar": peer.avatar})
    return jsonify({"status": "searching"})


@app.route('/api/stop_match', methods=['POST'])
@login_required
def stop_match():
    user = db.session.get(User, session['user_id'])
    if user:
        user.is_matching, user.matched_with_id = False, None
        db.session.commit()
    return jsonify({"ok": 1})


# ==========================================
# 动态朋友圈与收藏 API
# ==========================================

@app.route('/api/moments', methods=['GET', 'POST'])
@login_required
def handle_moments():
    uid = session['user_id']
    if request.method == 'POST':
        moment = Moment(user_id=uid, content=request.form.get('content', ''))
        file = request.files.get('image')
        if file and allowed_file(file.filename):
            save_name = f"moment_{datetime.now().strftime('%Y%m%d%H%M%S')}_{secure_filename(file.filename)}"
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], save_name))
            moment.image_path = save_name
        db.session.add(moment)
        db.session.commit()
        return jsonify({"ok": 1})
    else:
        moments = Moment.query.order_by(Moment.date_posted.desc()).all()
        res = []
        for m in moments:
            u = db.session.get(User, m.user_id)
            comments = Comment.query.filter_by(moment_id=m.id).order_by(Comment.date_posted.asc()).all()
            comments_data = [{"user": db.session.get(User, c.user_id).nickname, "content": c.content} for c in comments
                             if db.session.get(User, c.user_id)]
            local_time = m.date_posted.replace(tzinfo=timezone.utc).astimezone(tz=None)
            res.append({"id": m.id, "user": u.nickname if u else "?", "avatar": u.avatar if u else None,
                        "is_admin": u.is_admin if u else False, "time": local_time.strftime('%m-%d %H:%M'),
                        "content": m.content, "image": m.image_path, "likes": m.likes,
                        "is_liked": Like.query.filter_by(user_id=uid, moment_id=m.id).first() is not None,
                        "is_favorited": Favorite.query.filter_by(user_id=uid, moment_id=m.id).first() is not None,
                        "is_owner": m.user_id == uid, "comments": comments_data})
        return jsonify(res)


@app.route('/api/moments/<int:moment_id>', methods=['DELETE'])
@login_required
def delete_moment(moment_id):
    uid = session['user_id']
    user = db.session.get(User, uid)
    m = db.session.get(Moment, moment_id)
    if m and (m.user_id == uid or user.is_admin):
        Like.query.filter_by(moment_id=m.id).delete()
        Comment.query.filter_by(moment_id=m.id).delete()
        Favorite.query.filter_by(moment_id=m.id).delete()
        db.session.delete(m)
        db.session.commit()
        return jsonify({"ok": 1})
    return jsonify({"ok": 0, "error": "无权限或动态不存在"}), 403


@app.route('/api/moments/<int:moment_id>/like', methods=['POST'])
@login_required
def toggle_like(moment_id):
    uid = session['user_id']
    m = db.session.get(Moment, moment_id)
    if not m: return jsonify({"error": "not found"}), 404
    existing_like = Like.query.filter_by(user_id=uid, moment_id=m.id).first()
    if existing_like:
        db.session.delete(existing_like)
        m.likes = max(0, m.likes - 1)
        action = "unliked"
    else:
        db.session.add(Like(user_id=uid, moment_id=m.id))
        m.likes += 1
        action = "liked"
    db.session.commit()
    return jsonify({"ok": 1, "likes": m.likes, "action": action})


@app.route('/api/moments/<int:moment_id>/comment', methods=['POST'])
@login_required
def add_comment(moment_id):
    uid = session['user_id']
    content = request.form.get('content', '').strip()
    if content:
        c = Comment(user_id=uid, moment_id=moment_id, content=content)
        db.session.add(c)
        db.session.commit()
        return jsonify({"ok": 1})
    return jsonify({"ok": 0, "error": "内容不能为空"})


@app.route('/api/moments/<int:moment_id>/favorite', methods=['POST'])
@login_required
def toggle_favorite(moment_id):
    uid = session['user_id']
    m = db.session.get(Moment, moment_id)
    if not m: return jsonify({"error": "not found"}), 404
    existing_fav = Favorite.query.filter_by(user_id=uid, moment_id=m.id).first()
    if existing_fav:
        db.session.delete(existing_fav)
        action = "unfavorited"
    else:
        db.session.add(Favorite(user_id=uid, moment_id=m.id))
        action = "favorited"
    db.session.commit()
    return jsonify({"ok": 1, "action": action})


@app.route('/api/favorites', methods=['GET'])
@login_required
def get_favorites():
    uid = session['user_id']
    favs = Favorite.query.filter_by(user_id=uid).order_by(Favorite.date_favorited.desc()).all()
    moment_ids = [f.moment_id for f in favs]
    moments = Moment.query.filter(Moment.id.in_(moment_ids)).all()
    moments_dict = {m.id: m for m in moments}
    sorted_moments = [moments_dict[mid] for mid in moment_ids if mid in moments_dict]
    res = []
    for m in sorted_moments:
        u = db.session.get(User, m.user_id)
        local_time = m.date_posted.replace(tzinfo=timezone.utc).astimezone(tz=None)
        res.append({"id": m.id, "user": u.nickname if u else "?", "avatar": u.avatar if u else None,
                    "time": local_time.strftime('%m-%d %H:%M'), "content": m.content, "image": m.image_path})
    return jsonify(res)


if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(host='0.0.0.0', port=5000, debug=True)