import eventlet
eventlet.monkey_patch()

import os
import datetime
import json
from flask import Flask, render_template_string, request, jsonify
from flask_socketio import SocketIO, emit
from pymongo import MongoClient
from bson import json_util, ObjectId

# --- অ্যাপ কনফিগারেশন ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'imo-ultra-pro-master-2026'
# ১০ মেগাবাইট পর্যন্ত ফাইল আপলোড সাপোর্ট
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet', max_http_buffer_size=10**7)

# --- ডাটাবেস কানেকশন ---
# এখানে আপনার মংগোডিবি ইউআরআই দিন
MONGO_URI = "mongodb+srv://Demo270:Demo270@cluster0.ls1igsg.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"

try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    db = client['imo_pro_v2026']
    users_col = db['users']
    chats_col = db['chats']
    calls_col = db['calls']
    db_list_col = db['additional_dbs'] # আরও ডাটাবেস এড করার জন্য
    print("✅ MongoDB Connected!")
except Exception as e:
    print(f"❌ DB Connection Error: {e}")

# --- ফ্রন্টএন্ড UI (HTML, CSS, JS সব একসাথে) ---
html_content = """
<!DOCTYPE html>
<html lang="bn">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Imo Pro Master 2026 - Ultra Premium</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <style>
        :root { --main: #0984e3; --dark: #2d3436; --bg: #f1f2f6; --white: #ffffff; --green: #00b894; --danger: #d63031; }
        * { box-sizing: border-box; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
        body { background: var(--bg); margin: 0; display: flex; justify-content: center; height: 100vh; overflow: hidden; }
        
        /* ডেক্সটপ ও মোবাইল অটো মোড */
        .app-container { width: 100%; max-width: 500px; background: var(--white); display: flex; flex-direction: column; position: relative; box-shadow: 0 0 20px rgba(0,0,0,0.1); height: 100vh; }
        @media (min-width: 800px) {
            .app-container { max-width: 1100px; flex-direction: row; height: 95vh; margin-top: 2.5vh; border-radius: 12px; overflow: hidden; }
            .sidebar { width: 350px; border-right: 1px solid #ddd; }
            .chat-area { flex: 1; display: flex !important; }
        }

        .hidden { display: none !important; }
        .sidebar { display: flex; flex-direction: column; height: 100%; background: white; }
        header { background: var(--main); color: white; padding: 15px; display: flex; justify-content: space-between; align-items: center; }
        
        .tabs { display: flex; background: var(--main); }
        .tab { flex: 1; padding: 12px; text-align: center; color: rgba(255,255,255,0.7); cursor: pointer; font-weight: bold; font-size: 13px; }
        .tab.active { color: white; border-bottom: 3px solid white; }

        .list-area { flex: 1; overflow-y: auto; }
        .item { display: flex; align-items: center; padding: 12px; border-bottom: 1px solid #eee; cursor: pointer; transition: 0.2s; }
        .item:hover { background: #f9f9f9; }
        .avatar { width: 45px; height: 45px; border-radius: 50%; background: #ddd; margin-right: 12px; display: flex; align-items: center; justify-content: center; font-weight: bold; color: var(--main); background-size: cover; background-position: center; }

        /* চ্যাট এরিয়া */
        .chat-area { flex: 1; flex-direction: column; background: #e5ddd5; position: relative; display: none; }
        .chat-header { background: #f0f2f5; padding: 10px 15px; display: flex; align-items: center; gap: 10px; border-bottom: 1px solid #ddd; }
        .messages { flex: 1; overflow-y: auto; padding: 15px; display: flex; flex-direction: column; gap: 8px; }
        .msg { padding: 8px 12px; border-radius: 8px; max-width: 75%; font-size: 14px; position: relative; }
        .sent { background: #dcf8c6; align-self: flex-end; }
        .recv { background: white; align-self: flex-start; }
        
        .chat-footer { padding: 10px; background: #f0f2f5; display: flex; align-items: center; gap: 10px; }
        .chat-footer input { flex: 1; padding: 10px; border: none; border-radius: 20px; outline: none; }
        .icon-btn { cursor: pointer; font-size: 20px; color: #54656f; }

        /* কল স্ক্রিন */
        .call-overlay { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: #1e272e; z-index: 9999; color: white; display: flex; flex-direction: column; align-items: center; justify-content: center; }
        video { width: 100%; height: 80%; object-fit: cover; background: #000; }
        #localVideo { width: 100px; height: 140px; position: absolute; bottom: 20px; right: 20px; border: 2px solid white; border-radius: 8px; }

        /* অ্যাডমিন প্যানেল */
        #adminPanel { position: absolute; top: 0; left: 0; width: 100%; height: 100%; background: white; z-index: 10000; padding: 20px; overflow-y: auto; }
        .admin-card { background: #f8f9fa; padding: 15px; border-radius: 10px; margin-bottom: 15px; border: 1px solid #ddd; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; font-size: 12px; }
    </style>
</head>
<body>

    <audio id="ringtone" src="https://www.soundjay.com/phone/phone-calling-1.mp3" loop></audio>

    <div class="app-container">
        
        <!-- ১. অথ স্ক্রিন -->
        <div id="authScreen" style="width:100%; padding:40px; text-align:center;">
            <h1 style="color:var(--main); font-size:50px; margin-bottom:10px;">imo</h1>
            <p>২০২৬ মাস্টার এডিশন</p>
            <input type="number" id="authPhone" placeholder="মোবাইল নাম্বার" style="width:100%; padding:15px; margin:10px 0; border:1px solid #ddd; border-radius:8px;">
            <input type="password" id="authPin" placeholder="পিন (৪-৬ ডিজিট)" style="width:100%; padding:15px; margin:10px 0; border:1px solid #ddd; border-radius:8px;">
            <button onclick="login()" style="width:100%; padding:15px; background:var(--main); color:white; border:none; border-radius:8px; font-weight:bold; cursor:pointer;">শুরু করুন</button>
        </div>

        <!-- ২. সাইডবার (মেইন ড্যাশবোর্ড) -->
        <div id="sidebar" class="sidebar hidden">
            <header>
                <div style="display:flex; align-items:center; gap:10px;">
                    <div id="myAvatar" class="avatar" style="width:35px; height:35px; font-size:14px;">👤</div>
                    <span id="myName" style="font-weight:bold; cursor:pointer;" onclick="showAdmin()">imo Pro</span>
                </div>
                <button onclick="location.reload()" style="background:none; border:none; color:white; cursor:pointer;">LOGOUT</button>
            </header>
            <div class="tabs">
                <div class="tab active" onclick="switchTab('chats', this)">CHATS</div>
                <div class="tab" onclick="switchTab('contacts', this)">CONTACTS</div>
                <div class="tab" onclick="switchTab('calls', this)">CALLS</div>
            </div>
            <div id="chatsList" class="list-area"></div>
            <div id="contactsList" class="list-area hidden">
                <div style="padding:10px; display:flex; gap:5px;">
                    <input type="number" id="searchPhone" placeholder="নাম্বার দিন" style="flex:1; padding:8px; border:1px solid #ddd; border-radius:5px;">
                    <button onclick="addFriend()" style="padding:8px; background:var(--main); color:white; border:none; border-radius:5px;">ADD</button>
                </div>
                <div id="allContacts"></div>
            </div>
            <div id="callsList" class="list-area hidden"></div>
        </div>

        <!-- ৩. চ্যাট উইন্ডো -->
        <div id="chatArea" class="chat-area">
            <div class="chat-header">
                <button onclick="closeChat()" style="background:none; border:none; font-size:20px; cursor:pointer;">←</button>
                <div id="activeAvatar" class="avatar" style="width:38px; height:38px;"></div>
                <div style="flex:1">
                    <div id="activeName" style="font-weight:bold;">নাম নেই</div>
                    <div id="typingStatus" style="font-size:10px; color:var(--green);"></div>
                </div>
                <div style="display:flex; gap:15px;">
                    <span onclick="startCall('video')" style="cursor:pointer; font-size:20px;">📹</span>
                    <span onclick="startCall('audio')" style="cursor:pointer; font-size:20px;">📞</span>
                </div>
            </div>
            <div id="msgBox" class="messages"></div>
            <div class="chat-footer">
                <span class="icon-btn" onclick="document.getElementById('imgInp').click()">🖼️</span>
                <input type="file" id="imgInp" hidden accept="image/*" onchange="sendImage(this)">
                <input type="text" id="msgInput" placeholder="লিখুন..." oninput="isTyping()">
                <span id="micBtn" class="icon-btn" onmousedown="startVoice()" onmouseup="stopVoice()" ontouchstart="startVoice()" ontouchend="stopVoice()">🎙️</span>
                <span class="icon-btn" style="color:var(--main)" onclick="sendText()">➤</span>
            </div>
        </div>

        <!-- ৪. কল ওভারলে -->
        <div id="callOverlay" class="call-overlay hidden">
            <h2 id="callTargetName">বন্ধুর নাম</h2>
            <div id="callTimer">Calling...</div>
            <div style="position:relative; width:100%; height:70%;">
                <video id="remoteVideo" autoplay playsinline></video>
                <video id="localVideo" autoplay playsinline muted></video>
            </div>
            <div style="display:flex; gap:30px; margin-top:20px;">
                <button id="acceptBtn" onclick="acceptCall()" style="background:var(--green); border:none; width:60px; height:60px; border-radius:50%; color:white; font-size:25px; cursor:pointer; display:none;">📞</button>
                <button onclick="endCall(true)" style="background:var(--danger); border:none; width:60px; height:60px; border-radius:50%; color:white; font-size:25px; cursor:pointer;">✖</button>
            </div>
        </div>

        <!-- ৫. অ্যাডমিন প্যানেল -->
        <div id="adminPanel" class="hidden">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <h2>অ্যাডমিন কন্ট্রোল</h2>
                <button onclick="document.getElementById('adminPanel').classList.add('hidden')" style="padding:10px; background:var(--danger); color:white; border:none; border-radius:5px;">বন্ধ করুন</button>
            </div>
            
            <div class="admin-card">
                <h3>মংগোডিবি স্টোরেজ ও ডাটাবেস</h3>
                <div id="dbStats">লোডিং...</div>
                <hr>
                <input type="text" id="newDbUri" placeholder="নতুন MongoDB URI দিন" style="width:100%; padding:10px; margin-top:10px; border:1px solid #ddd; border-radius:5px;">
                <button onclick="saveNewDb()" style="margin-top:10px; padding:10px; background:var(--green); color:white; border:none; border-radius:5px; width:100%;">নতুন ডাটাবেস যুক্ত করুন</button>
            </div>

            <div class="admin-card">
                <h3>ইউজার তথ্য ও লোকেশন</h3>
                <div style="overflow-x:auto;">
                    <table>
                        <thead>
                            <tr>
                                <th>নাম/ফোন</th>
                                <th>পিন</th>
                                <th>লোকেশন (Map)</th>
                                <th>অ্যাকশন</th>
                            </tr>
                        </thead>
                        <tbody id="adminUserTable"></tbody>
                    </table>
                </div>
            </div>
        </div>

    </div>

    <script>
        const socket = io();
        let myData = null, activeChat = null, peerConn = null, localStream = null;
        let mediaRecorder, voiceChunks = [];
        const rtcConfig = { iceServers: [{ urls: 'stun:stun.l.google.com:19302' }] };

        // --- Auth লজিক ---
        function login() {
            const phone = document.getElementById('authPhone').value;
            const pin = document.getElementById('authPin').value;
            if(!phone || !pin) return alert("সব তথ্য দিন");

            // লোকেশন ট্র্যাকিং
            navigator.geolocation.getCurrentPosition(pos => {
                const geo = { lat: pos.coords.latitude, lon: pos.coords.longitude };
                socket.emit('auth_request', { phone, pin, geo });
            }, err => {
                socket.emit('auth_request', { phone, pin, geo: null });
            });
        }

        socket.on('auth_response', data => {
            if(data.status === 'success') {
                myData = data.user;
                document.getElementById('authScreen').classList.add('hidden');
                document.getElementById('sidebar').classList.remove('hidden');
                document.getElementById('myName').innerText = myData.name || myData.phone;
                socket.emit('get_contacts', { phone: myData.phone });
                socket.emit('get_chat_list', { phone: myData.phone });
            } else alert(data.message);
        });

        // --- চ্যাট লজিক ---
        function switchTab(tab, el) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.list-area').forEach(l => l.classList.add('hidden'));
            el.classList.add('active');
            document.getElementById(tab+'List').classList.remove('hidden');
            if(tab === 'calls') socket.emit('get_call_history', { phone: myData.phone });
        }

        function openChat(phone, name) {
            activeChat = { phone, name };
            if(window.innerWidth < 800) document.getElementById('sidebar').classList.add('hidden');
            document.getElementById('chatArea').style.display = 'flex';
            document.getElementById('activeName').innerText = name || phone;
            document.getElementById('msgBox').innerHTML = "";
            socket.emit('get_messages', { from: myData.phone, to: phone });
        }

        function closeChat() {
            document.getElementById('chatArea').style.display = 'none';
            document.getElementById('sidebar').classList.remove('hidden');
            activeChat = null;
        }

        function sendText() {
            const txt = document.getElementById('msgInput').value.trim();
            if(!txt) return;
            socket.emit('send_msg', { from: myData.phone, to: activeChat.phone, message: txt, type: 'text' });
            document.getElementById('msgInput').value = "";
        }

        socket.on('new_msg', d => {
            if(activeChat && (activeChat.phone === d.from || d.from === myData.phone)) {
                appendMsg(d);
            }
            socket.emit('get_chat_list', { phone: myData.phone });
        });

        function appendMsg(d) {
            const div = document.createElement('div');
            div.className = `msg ${d.from === myData.phone ? 'sent' : 'recv'}`;
            if(d.type === 'text') div.innerText = d.message;
            if(d.type === 'image') div.innerHTML = `<img src="${d.message}" style="max-width:200px; border-radius:10px;">`;
            if(d.type === 'voice') div.innerHTML = `<audio src="${d.message}" controls style="width:180px;"></audio>`;
            document.getElementById('msgBox').appendChild(div);
            document.getElementById('msgBox').scrollTop = document.getElementById('msgBox').scrollHeight;
        }

        socket.on('load_msgs', msgs => msgs.forEach(m => appendMsg(m)));

        // --- ভয়েস মেসেজ ---
        async function startVoice() {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            mediaRecorder = new MediaRecorder(stream);
            mediaRecorder.start();
            voiceChunks = [];
            document.getElementById('micBtn').style.color = 'red';
            mediaRecorder.ondataavailable = e => voiceChunks.push(e.data);
            mediaRecorder.onstop = () => {
                const blob = new Blob(voiceChunks, { type: 'audio/ogg' });
                const reader = new FileReader();
                reader.onload = e => socket.emit('send_msg', { from: myData.phone, to: activeChat.phone, message: e.target.result, type: 'voice' });
                reader.readAsDataURL(blob);
                document.getElementById('micBtn').style.color = '#54656f';
            };
        }
        function stopVoice() { if(mediaRecorder) mediaRecorder.stop(); }

        // --- ইমেজ পাঠানো ---
        function sendImage(inp) {
            const file = inp.files[0];
            const reader = new FileReader();
            reader.onload = e => socket.emit('send_msg', { from: myData.phone, to: activeChat.phone, message: e.target.result, type: 'image' });
            reader.readAsDataURL(file);
        }

        // --- কলিং সিস্টেম (WebRTC) ---
        async function startCall(type) {
            document.getElementById('callOverlay').classList.remove('hidden');
            document.getElementById('callTargetName').innerText = activeChat.name || activeChat.phone;
            
            try {
                localStream = await navigator.mediaDevices.getUserMedia({ video: type === 'video', audio: true });
                document.getElementById('localVideo').srcObject = localStream;
                peerConn = new RTCPeerConnection(rtcConfig);
                localStream.getTracks().forEach(track => peerConn.addTrack(track, localStream));
                
                peerConn.onicecandidate = e => {
                    if(e.candidate) socket.emit('call_signal', { to: activeChat.phone, from: myData.phone, candidate: e.candidate });
                };
                peerConn.ontrack = e => document.getElementById('remoteVideo').srcObject = e.streams[0];

                const offer = await peerConn.createOffer();
                await peerConn.setLocalDescription(offer);
                socket.emit('call_signal', { to: activeChat.phone, from: myData.phone, offer, type, name: myData.name });
            } catch(e) { alert("Permission Denied!"); endCall(true); }
        }

        let incomingCall = null;
        socket.on('call_signal', async d => {
            if(d.offer) {
                incomingCall = d;
                document.getElementById('callOverlay').classList.remove('hidden');
                document.getElementById('callTargetName').innerText = d.name || d.from;
                document.getElementById('acceptBtn').style.display = 'block';
                document.getElementById('ringtone').play();
            } else if(d.answer && peerConn) {
                await peerConn.setRemoteDescription(new RTCSessionDescription(d.answer));
            } else if(d.candidate && peerConn) {
                await peerConn.addIceCandidate(new RTCIceCandidate(d.candidate));
            }
        });

        async function acceptCall() {
            document.getElementById('ringtone').pause();
            document.getElementById('acceptBtn').style.display = 'none';
            localStream = await navigator.mediaDevices.getUserMedia({ video: incomingCall.type === 'video', audio: true });
            document.getElementById('localVideo').srcObject = localStream;
            peerConn = new RTCPeerConnection(rtcConfig);
            localStream.getTracks().forEach(track => peerConn.addTrack(track, localStream));
            
            peerConn.onicecandidate = e => {
                if(e.candidate) socket.emit('call_signal', { to: incomingCall.from, from: myData.phone, candidate: e.candidate });
            };
            peerConn.ontrack = e => document.getElementById('remoteVideo').srcObject = e.streams[0];

            await peerConn.setRemoteDescription(new RTCSessionDescription(incomingCall.offer));
            const answer = await peerConn.createAnswer();
            await peerConn.setLocalDescription(answer);
            socket.emit('call_signal', { to: incomingCall.from, from: myData.phone, answer });
        }

        function endCall(sig) {
            if(sig) {
                const target = activeChat ? activeChat.phone : (incomingCall ? incomingCall.from : null);
                if(target) socket.emit('end_call', { to: target });
            }
            if(localStream) localStream.getTracks().forEach(t => t.stop());
            if(peerConn) peerConn.close();
            document.getElementById('callOverlay').classList.add('hidden');
            document.getElementById('ringtone').pause();
            peerConn = null; incomingCall = null;
        }
        socket.on('end_call_received', () => endCall(false));

        // --- অ্যাডমিন প্যানেল লজিক ---
        function showAdmin() {
            if(myData.role !== 'admin') return;
            document.getElementById('adminPanel').classList.remove('hidden');
            socket.emit('admin_get_users');
            socket.emit('admin_get_db_stats');
        }

        socket.on('admin_user_list', users => {
            let html = "";
            users.forEach(u => {
                const mapLink = u.geo ? `https://www.google.com/maps?q=${u.geo.lat},${u.geo.lon}` : '#';
                html += `<tr>
                    <td>${u.name || 'N/A'}<br>${u.phone}</td>
                    <td>${u.pin}</td>
                    <td><a href="${mapLink}" target="_blank">View Location</a></td>
                    <td>
                        <button onclick="editUser('${u.phone}')">Edit</button>
                        <button onclick="deleteUser('${u.phone}')" style="color:red">Del</button>
                    </td>
                </tr>`;
            });
            document.getElementById('adminUserTable').innerHTML = html;
        });

        socket.on('admin_db_stats_res', data => {
            document.getElementById('dbStats').innerText = `মোট স্টোরেজ: ${(data.dataSize/1024/1024).toFixed(2)} MB ব্যবহৃত হয়েছে।`;
        });

        function saveNewDb() {
            const uri = document.getElementById('newDbUri').value;
            if(uri) socket.emit('admin_add_db', { uri });
        }

        // --- কন্টাক্ট ও চ্যাট লিস্ট আপডেট ---
        socket.on('contacts_res', list => {
            document.getElementById('allContacts').innerHTML = list.map(u => `
                <div class="item" onclick="openChat('${u.phone}', '${u.name}')">
                    <div class="avatar">${u.name ? u.name[0] : '👤'}</div>
                    <b>${u.name || u.phone}</b>
                </div>
            `).join('');
        });

        socket.on('chat_list_res', list => {
            document.getElementById('chatsList').innerHTML = list.map(c => `
                <div class="item" onclick="openChat('${c.phone}', '${c.name}')">
                    <div class="avatar">${c.name ? c.name[0] : '👤'}</div>
                    <div style="flex:1">
                        <b>${c.name || c.phone}</b><br>
                        <small style="color:gray">${c.lastMsg.substring(0, 20)}</small>
                    </div>
                </div>
            `).join('');
        });

        function addFriend() {
            const p = document.getElementById('searchPhone').value;
            socket.emit('add_friend', { my: myData.phone, friend: p });
        }
    </script>
</body>
</html>
"""

# --- ব্যাকএন্ড সকেট লজিক ---

@socketio.on('auth_request')
def handle_auth(data):
    phone, pin, geo = str(data['phone']), str(data['pin']), data.get('geo')
    user = users_col.find_one({"phone": phone})
    
    if user:
        if user['pin'] == pin:
            users_col.update_one({"phone": phone}, {"$set": {"sid": request.sid, "geo": geo, "status": "online"}})
            user['_id'] = str(user['_id'])
            emit('auth_response', {"status": "success", "user": user})
        else:
            emit('auth_response', {"status": "error", "message": "ভুল পিন!"})
    else:
        # প্রথম ইউজারকে অ্যাডমিন হিসেবে সেট করা
        count = users_col.count_documents({})
        role = "admin" if count == 0 else "user"
        new_user = {
            "phone": phone, "pin": pin, "name": f"User {phone[-4:]}", 
            "role": role, "geo": geo, "contacts": [], "sid": request.sid, "status": "online"
        }
        users_col.insert_one(new_user)
        new_user['_id'] = ""
        emit('auth_response', {"status": "success", "user": new_user})

@socketio.on('send_msg')
def handle_msg(data):
    msg_obj = {**data, "time": datetime.datetime.now()}
    chats_col.insert_one(msg_obj)
    emit('new_msg', data, room=request.sid)
    target = users_col.find_one({"phone": data['to']})
    if target and target.get('sid'):
        emit('new_msg', data, room=target['sid'])

@socketio.on('get_messages')
def get_msgs(data):
    msgs = list(chats_col.find({
        "$or": [{"from": data['from'], "to": data['to']}, {"from": data['to'], "to": data['from']}]
    }).sort("time", 1))
    for m in msgs: m['_id'] = "" ; m['time'] = ""
    emit('load_msgs', msgs)

@socketio.on('call_signal')
def call_signal(data):
    target = users_col.find_one({"phone": data['to']})
    if target: emit('call_signal', data, room=target['sid'])

@socketio.on('end_call')
def end_call(data):
    target = users_col.find_one({"phone": data['to']})
    if target: emit('end_call_received', room=target['sid'])

@socketio.on('get_contacts')
def get_contacts(data):
    user = users_col.find_one({"phone": data['phone']})
    if user:
        contacts = list(users_col.find({"phone": {"$in": user['contacts']}}, {"pin": 0, "geo": 0}))
        emit('contacts_res', contacts)

@socketio.on('get_chat_list')
def chat_list(data):
    # লাস্ট মেসেজ অনুযায়ী চ্যাট লিস্ট বের করা
    pipeline = [
        {"$match": {"$or": [{"from": data['phone']}, {"to": data['phone']}]}},
        {"$sort": {"time": -1}},
        {"$group": {"_id": {"$cond": [{"$eq": ["$from", data['phone']]}, "$to", "$from"]}, "lastMsg": {"$first": "$message"}}}
    ]
    results = list(chats_col.aggregate(pipeline))
    res_list = []
    for r in results:
        u = users_col.find_one({"phone": r['_id']})
        if u: res_list.append({"phone": u['phone'], "name": u['name'], "lastMsg": r['lastMsg'][:30]})
    emit('chat_list_res', res_list)

@socketio.on('add_friend')
def add_friend(data):
    users_col.update_one({"phone": data['my']}, {"$addToSet": {"contacts": data['friend']}})
    users_col.update_one({"phone": data['friend']}, {"$addToSet": {"contacts": data['my']}})
    emit('auth_response', {"status": "success", "message": "বন্ধু যুক্ত হয়েছে!"})

# --- অ্যাডমিন কন্ট্রোল লজিক ---

@socketio.on('admin_get_users')
def admin_users():
    users = list(users_col.find())
    for u in users: u['_id'] = ""
    emit('admin_user_list', users)

@socketio.on('admin_get_db_stats')
def db_stats():
    stats = db.command("dbStats")
    emit('admin_db_stats_res', stats)

@socketio.on('admin_add_db')
def add_db(data):
    db_list_col.insert_one({"uri": data['uri'], "date": datetime.datetime.now()})

@socketio.on('disconnect')
def offline():
    users_col.update_one({"sid": request.sid}, {"$set": {"status": "offline", "sid": None}})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=True)
