import eventlet
eventlet.monkey_patch()

import os
import datetime
import json
from flask import Flask, render_template_string, request
from flask_socketio import SocketIO, emit
from pymongo import MongoClient
from bson import json_util

# --- অ্যাপ কনফিগারেশন ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'imo-pro-v3-2026'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet', max_http_buffer_size=10**7) # ১০ মেগাবাইট পর্যন্ত ফাইল সাপোর্ট

# --- ডাটাবেস কানেকশন ---
MONGO_URI = "mongodb+srv://Demo270:Demo270@cluster0.ls1igsg.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0" 

try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    db = client['imo_pro_v3']
    users_col = db['users']
    chats_col = db['chats']
    client.admin.command('ping')
    print("✅ MongoDB Connected!")
except Exception as e:
    print(f"❌ DB Error: {e}")

# --- ফ্রন্টএন্ড UI (HTML, CSS, JS) ---
html_content = """
<!DOCTYPE html>
<html lang="bn">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Imo Pro - মেসেঞ্জার</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <style>
        :root { --main: #2e86de; --bg: #f1f2f6; --white: #ffffff; --grey: #8395a7; --green: #10ac84; }
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: var(--bg); margin: 0; display: flex; justify-content: center; height: 100vh; }
        .hidden { display: none !important; }
        
        .app-container { width: 100%; max-width: 450px; background: var(--white); display: flex; flex-direction: column; position: relative; box-shadow: 0 0 20px rgba(0,0,0,0.1); overflow: hidden; }
        
        /* Auth & Profile Setup */
        .screen { padding: 30px 20px; text-align: center; height: 100%; overflow-y: auto; box-sizing: border-box; }
        input { width: 100%; padding: 14px; margin: 10px 0; border: 1px solid #ddd; border-radius: 10px; font-size: 16px; box-sizing: border-box; }
        .btn { width: 100%; padding: 14px; border: none; border-radius: 10px; cursor: pointer; font-weight: bold; font-size: 16px; margin-top: 10px; background: var(--main); color: white; }

        /* Header */
        header { background: var(--main); color: white; padding: 15px; display: flex; justify-content: space-between; align-items: center; font-size: 18px; font-weight: bold; }
        
        /* Tabs */
        .tabs { display: flex; background: var(--main); border-bottom: 2px solid rgba(0,0,0,0.1); }
        .tab { flex: 1; padding: 12px; text-align: center; color: rgba(255,255,255,0.7); cursor: pointer; font-weight: bold; }
        .tab.active { color: white; border-bottom: 3px solid white; }

        /* List Area */
        .list-container { flex: 1; overflow-y: auto; }
        .item { display: flex; align-items: center; padding: 15px; border-bottom: 1px solid #f0f0f0; cursor: pointer; position: relative; }
        .item:hover { background: #f9f9f9; }
        .avatar { width: 50px; height: 50px; border-radius: 50%; background: #ddd; margin-right: 15px; overflow: hidden; display: flex; align-items: center; justify-content: center; font-size: 20px; color: #666; object-fit: cover; }
        .item-info { flex: 1; }
        .item-info b { display: block; font-size: 16px; color: #333; }
        .item-info span { font-size: 13px; color: var(--grey); }
        .online-dot { width: 12px; height: 12px; background: var(--green); border-radius: 50%; border: 2px solid white; position: absolute; left: 50px; top: 50px; }

        /* Chat Window */
        #chatView { position: absolute; top: 0; left: 0; width: 100%; height: 100%; background: #e5ddd5; z-index: 1000; display: flex; flex-direction: column; }
        .chat-header { background: var(--main); color: white; padding: 10px 15px; display: flex; align-items: center; gap: 15px; }
        .chat-msgs { flex: 1; padding: 15px; overflow-y: auto; display: flex; flex-direction: column; gap: 8px; }
        .msg { padding: 10px 14px; border-radius: 12px; max-width: 80%; font-size: 15px; position: relative; word-wrap: break-word; box-shadow: 0 1px 1px rgba(0,0,0,0.1); }
        .msg.sent { background: #dcf8c6; align-self: flex-end; border-bottom-right-radius: 2px; }
        .msg.recv { background: white; align-self: flex-start; border-bottom-left-radius: 2px; }
        .msg img { max-width: 100%; border-radius: 8px; margin-top: 5px; }
        .msg-time { font-size: 10px; color: #999; display: block; text-align: right; margin-top: 3px; }

        .chat-footer { background: #f0f0f0; padding: 10px; display: flex; align-items: center; gap: 10px; }
        .chat-footer input { margin: 0; border-radius: 25px; border: none; padding: 12px 20px; }
        .icon-btn { cursor: pointer; font-size: 22px; color: var(--main); }

        /* Call Overlay */
        .call-overlay { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: #075e54; z-index: 9999; color: white; display: flex; flex-direction: column; align-items: center; justify-content: center; }
        .video-box { width: 100%; height: 70%; position: relative; background: #000; }
        #remoteVideo { width: 100%; height: 100%; object-fit: cover; }
        #localVideo { width: 100px; height: 150px; position: absolute; bottom: 20px; right: 20px; border: 2px solid white; border-radius: 8px; z-index: 10; }
        .call-actions { margin-top: 30px; display: flex; gap: 30px; }
        .call-btn { width: 70px; height: 70px; border-radius: 50%; border: none; display: flex; align-items: center; justify-content: center; font-size: 30px; cursor: pointer; color: white; }
        .btn-reject { background: #ff4757; }
        .btn-accept { background: #2ecc71; }
    </style>
</head>
<body>

    <audio id="ringtone" src="https://www.soundjay.com/phone/phone-calling-1.mp3" loop></audio>

    <div class="app-container">
        
        <!-- ১. অথ স্ক্রিন -->
        <div id="authScreen" class="screen">
            <h1 style="color: var(--main); font-size: 40px;">imo</h1>
            <p>আপনার ফোন নম্বর দিয়ে লগইন করুন</p>
            <input type="number" id="authPhone" placeholder="মোবাইল নাম্বার">
            <input type="password" id="authPin" placeholder="৫ ডিজিট পিন">
            <button class="btn" onclick="auth()">চালিয়ে যান</button>
        </div>

        <!-- ২. প্রোফাইল সেটআপ -->
        <div id="profileScreen" class="screen hidden">
            <h2>প্রোফাইল সেটআপ</h2>
            <div id="avatarPreview" class="avatar" style="width: 100px; height: 100px; margin: 0 auto 20px;">👤</div>
            <input type="text" id="setupName" placeholder="আপনার নাম">
            <p>একটি প্রোফাইল ছবি চুজ করুন (লিঙ্ক বা ফাইল)</p>
            <input type="file" id="avatarFile" accept="image/*" onchange="previewAvatar(event)">
            <button class="btn" onclick="saveProfile()">সম্পন্ন করুন</button>
        </div>

        <!-- ৩. মেইন ড্যাশবোর্ড -->
        <div id="mainDashboard" class="hidden" style="display: flex; flex-direction: column; height: 100%;">
            <header>
                <span>imo</span>
                <span onclick="logout()" style="font-size: 14px; cursor: pointer;">লগআউট</span>
            </header>
            <div class="tabs">
                <div class="tab active" onclick="switchTab('chats')">চ্যাটস</div>
                <div class="tab" onclick="switchTab('contacts')">কন্টাক্টস</div>
            </div>
            
            <div id="chatsTab" class="list-container">
                <!-- চ্যাট লিস্ট এখানে আসবে -->
            </div>

            <div id="contactsTab" class="list-container hidden">
                <div style="padding: 10px;">
                    <input type="number" id="searchUser" placeholder="বন্ধুর নাম্বার দিয়ে খুঁজুন" oninput="searchContacts()">
                </div>
                <div id="contactList"></div>
            </div>
        </div>

        <!-- ৪. চ্যাট উইন্ডো -->
        <div id="chatView" class="hidden">
            <div class="chat-header">
                <span onclick="closeChat()" style="cursor:pointer; font-size: 24px;">←</span>
                <img id="chatAvatar" class="avatar" style="width: 40px; height: 40px; margin: 0;">
                <div style="flex: 1;">
                    <div id="chatName" style="font-weight: bold;">নাম</div>
                    <div id="typingStatus" style="font-size: 11px; opacity: 0.8;"></div>
                </div>
                <span onclick="startCall('video')" class="icon-btn" style="color:white;">📹</span>
                <span onclick="startCall('audio')" class="icon-btn" style="color:white;">📞</span>
            </div>
            <div id="chatBox" class="chat-msgs"></div>
            <div class="chat-footer">
                <label for="imgUpload" class="icon-btn">🖼️</label>
                <input type="file" id="imgUpload" hidden accept="image/*" onchange="sendImage(event)">
                <input type="text" id="msgInput" placeholder="মেসেজ লিখুন..." oninput="handleTyping()">
                <span class="icon-btn" onclick="sendText()">➤</span>
            </div>
        </div>

        <!-- ৫. কল ওভারলে -->
        <div id="callOverlay" class="call-overlay hidden">
            <h2 id="callTargetName">বন্ধুর নাম</h2>
            <p id="callStatus">কল হচ্ছে...</p>
            <div id="videoContainer" class="video-box hidden">
                <video id="remoteVideo" autoplay playsinline></video>
                <video id="localVideo" autoplay playsinline muted></video>
            </div>
            <div class="call-actions">
                <button id="btnAccept" class="call-btn btn-accept hidden" onclick="acceptCall()">📞</button>
                <button class="call-btn btn-reject" onclick="endCall()">✖</button>
            </div>
        </div>

    </div>

    <script>
        const socket = io();
        let myData = null;
        let activeChat = null;
        let peerConn, localStream;
        let typingTimeout;
        const rtcConfig = { iceServers: [{ urls: 'stun:stun.l.google.com:19302' }] };

        // --- অটো লগইন ---
        window.onload = () => {
            const saved = localStorage.getItem('imo_v3_session');
            if (saved) socket.emit('auto_login', JSON.parse(saved));
        };

        function auth() {
            const phone = document.getElementById('authPhone').value.trim();
            const pin = document.getElementById('authPin').value.trim();
            if (phone.length < 5 || pin.length < 4) return alert("সঠিক তথ্য দিন");
            socket.emit('auth_request', { phone, pin });
        }

        socket.on('auth_response', data => {
            if (data.status === 'success') {
                myData = data.user;
                localStorage.setItem('imo_v3_session', JSON.stringify({ phone: data.user.phone, pin: data.user.pin }));
                document.getElementById('authScreen').classList.add('hidden');
                
                if (!data.user.name) {
                    document.getElementById('profileScreen').classList.remove('hidden');
                } else {
                    showDashboard();
                }
            } else {
                alert(data.message);
            }
        });

        function saveProfile() {
            const name = document.getElementById('setupName').value.trim();
            const avatar = document.getElementById('avatarPreview').src || "";
            if (!name) return alert("নাম লিখুন");
            socket.emit('update_profile', { phone: myData.phone, name, avatar });
        }

        socket.on('profile_updated', user => {
            myData = user;
            document.getElementById('profileScreen').classList.add('hidden');
            showDashboard();
        });

        function showDashboard() {
            document.getElementById('mainDashboard').classList.remove('hidden');
            socket.emit('get_contacts');
            socket.emit('get_chat_list', { phone: myData.phone });
        }

        function switchTab(tab) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            event.target.classList.add('active');
            if (tab === 'chats') {
                document.getElementById('chatsTab').classList.remove('hidden');
                document.getElementById('contactsTab').classList.add('hidden');
            } else {
                document.getElementById('chatsTab').classList.add('hidden');
                document.getElementById('contactsTab').classList.remove('hidden');
            }
        }

        // --- কন্টাক্ট ও চ্যাট লিস্ট ---
        socket.on('contacts_data', users => {
            const list = document.getElementById('contactList');
            list.innerHTML = "";
            users.forEach(u => {
                if (u.phone === myData.phone) return;
                list.innerHTML += `
                    <div class="item" onclick="openChat('${u.phone}', '${u.name}', '${u.avatar}')">
                        <img class="avatar" src="${u.avatar || '👤'}">
                        <div class="item-info">
                            <b>${u.name}</b>
                            <span>${u.phone}</span>
                        </div>
                        ${u.status === 'online' ? '<div class="online-dot"></div>' : ''}
                    </div>`;
            });
        });

        socket.on('chat_list_data', chats => {
            const list = document.getElementById('chatsTab');
            list.innerHTML = "";
            chats.forEach(c => {
                list.innerHTML += `
                    <div class="item" onclick="openChat('${c.phone}', '${c.name}', '${c.avatar}')">
                        <img class="avatar" src="${c.avatar || '👤'}">
                        <div class="item-info">
                            <b>${c.name}</b>
                            <span style="${c.unread ? 'color:var(--main); font-weight:bold;' : ''}">${c.lastMsg}</span>
                        </div>
                    </div>`;
            });
        });

        // --- চ্যাট লজিক ---
        function openChat(phone, name, avatar) {
            activeChat = { phone, name, avatar };
            document.getElementById('chatView').classList.remove('hidden');
            document.getElementById('chatName').innerText = name;
            document.getElementById('chatAvatar').src = avatar || '👤';
            document.getElementById('chatBox').innerHTML = "";
            socket.emit('get_messages', { from: myData.phone, to: phone });
        }

        function closeChat() {
            document.getElementById('chatView').classList.add('hidden');
            activeChat = null;
        }

        function sendText() {
            const text = document.getElementById('msgInput').value.trim();
            if (!text) return;
            const msgData = { from: myData.phone, to: activeChat.phone, message: text, type: 'text' };
            socket.emit('send_msg', msgData);
            appendMessage(msgData, 'sent');
            document.getElementById('msgInput').value = "";
        }

        function sendImage(e) {
            const file = e.target.files[0];
            if (!file) return;
            const reader = new FileReader();
            reader.onload = function(event) {
                const msgData = { from: myData.phone, to: activeChat.phone, message: event.target.result, type: 'image' };
                socket.emit('send_msg', msgData);
                appendMessage(msgData, 'sent');
            };
            reader.readAsDataURL(file);
        }

        socket.on('new_msg', data => {
            if (activeChat && activeChat.phone === data.from) {
                appendMessage(data, 'recv');
                socket.emit('msg_seen', { from: data.from, to: myData.phone });
            } else {
                // নোটিফিকেশন বা চ্যাট লিস্ট আপডেট
                socket.emit('get_chat_list', { phone: myData.phone });
            }
        });

        socket.on('load_msgs', msgs => {
            msgs.forEach(m => appendMessage(m, m.from === myData.phone ? 'sent' : 'recv'));
        });

        function appendMessage(data, side) {
            const box = document.getElementById('chatBox');
            const div = document.createElement('div');
            div.className = `msg ${side}`;
            
            let content = data.type === 'text' ? data.message : `<img src="${data.message}" onclick="window.open(this.src)">`;
            div.innerHTML = `${content} <span class="msg-time">${new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</span>`;
            
            box.appendChild(div);
            box.scrollTop = box.scrollHeight;
        }

        function handleTyping() {
            socket.emit('typing', { from: myData.phone, to: activeChat.phone });
        }

        socket.on('user_typing', data => {
            if (activeChat && activeChat.phone === data.from) {
                const status = document.getElementById('typingStatus');
                status.innerText = "typing...";
                clearTimeout(typingTimeout);
                typingTimeout = setTimeout(() => status.innerText = "", 2000);
            }
        });

        // --- ভিডিও কলিং লজিক (WebRTC) ---
        async function startCall(type) {
            document.getElementById('callOverlay').classList.remove('hidden');
            document.getElementById('callTargetName').innerText = activeChat.name;
            document.getElementById('callStatus').innerText = "Calling...";
            
            if (type === 'video') document.getElementById('videoContainer').classList.remove('hidden');

            localStream = await navigator.mediaDevices.getUserMedia({ video: type === 'video', audio: true });
            document.getElementById('localVideo').srcObject = localStream;

            peerConn = new RTCPeerConnection(rtcConfig);
            localStream.getTracks().forEach(track => peerConn.addTrack(track, localStream));

            peerConn.onicecandidate = e => {
                if (e.candidate) socket.emit('call_signal', { to: activeChat.phone, from: myData.phone, candidate: e.candidate });
            };
            peerConn.ontrack = e => {
                document.getElementById('remoteVideo').srcObject = e.streams[0];
            };

            const offer = await peerConn.createOffer();
            await peerConn.setLocalDescription(offer);
            socket.emit('call_signal', { to: activeChat.phone, from: myData.phone, offer, type, name: myData.name });
        }

        let incomingSignal = null;
        socket.on('call_signal', async data => {
            if (data.offer) {
                incomingSignal = data;
                document.getElementById('callOverlay').classList.remove('hidden');
                document.getElementById('callTargetName').innerText = data.name;
                document.getElementById('callStatus').innerText = `Incoming ${data.type} call...`;
                document.getElementById('btnAccept').classList.remove('hidden');
                document.getElementById('ringtone').play();
            } else if (data.answer) {
                await peerConn.setRemoteDescription(new RTCSessionDescription(data.answer));
                document.getElementById('callStatus').innerText = "Connected";
            } else if (data.candidate) {
                try { await peerConn.addIceCandidate(new RTCIceCandidate(data.candidate)); } catch(e) {}
            }
        });

        async function acceptCall() {
            document.getElementById('ringtone').pause();
            document.getElementById('btnAccept').classList.add('hidden');
            document.getElementById('callStatus').innerText = "Connecting...";
            if (incomingSignal.type === 'video') document.getElementById('videoContainer').classList.remove('hidden');

            localStream = await navigator.mediaDevices.getUserMedia({ video: incomingSignal.type === 'video', audio: true });
            document.getElementById('localVideo').srcObject = localStream;

            peerConn = new RTCPeerConnection(rtcConfig);
            localStream.getTracks().forEach(track => peerConn.addTrack(track, localStream));

            peerConn.onicecandidate = e => {
                if (e.candidate) socket.emit('call_signal', { to: incomingSignal.from, from: myData.phone, candidate: e.candidate });
            };
            peerConn.ontrack = e => {
                document.getElementById('remoteVideo').srcObject = e.streams[0];
            };

            await peerConn.setRemoteDescription(new RTCSessionDescription(incomingSignal.offer));
            const answer = await peerConn.createAnswer();
            await peerConn.setLocalDescription(answer);
            socket.emit('call_signal', { to: incomingSignal.from, from: myData.phone, answer });
        }

        function endCall() {
            location.reload(); // সিম্পল হ্যান্ডলিং এর জন্য পেজ রিলোড
        }

        function previewAvatar(e) {
            const file = e.target.files[0];
            if (file) {
                const reader = new FileReader();
                reader.onload = (event) => document.getElementById('avatarPreview').innerHTML = `<img src="${event.target.result}" style="width:100%; height:100%; border-radius:50%;">`;
                reader.readAsDataURL(file);
            }
        }

        function logout() {
            localStorage.removeItem('imo_v3_session');
            location.reload();
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(html_content)

# --- ব্যাকএন্ড সকেট লজিক ---

@socketio.on('auth_request')
def handle_auth(data):
    phone, pin = str(data.get('phone')), str(data.get('pin'))
    user = users_col.find_one({"phone": phone})
    if user:
        if user['pin'] == pin:
            users_col.update_one({"phone": phone}, {"$set": {"status": "online", "sid": request.sid}})
            user['_id'] = str(user['_id'])
            emit('auth_response', {"status": "success", "user": user})
        else:
            emit('auth_response', {"status": "error", "message": "ভুল পিন!"})
    else:
        new_user = {"phone": phone, "pin": pin, "name": "", "avatar": "", "status": "online", "sid": request.sid}
        users_col.insert_one(new_user)
        new_user['_id'] = str(new_user['_id'])
        emit('auth_response', {"status": "success", "user": new_user})
    broadcast_contacts()

@socketio.on('auto_login')
def auto_login(data):
    user = users_col.find_one({"phone": data['phone'], "pin": data['pin']})
    if user:
        users_col.update_one({"phone": data['phone']}, {"$set": {"status": "online", "sid": request.sid}})
        user['_id'] = str(user['_id'])
        emit('auth_response', {"status": "success", "user": user})
    broadcast_contacts()

@socketio.on('update_profile')
def update_profile(data):
    users_col.update_one({"phone": data['phone']}, {"$set": {"name": data['name'], "avatar": data['avatar']}})
    user = users_col.find_one({"phone": data['phone']})
    user['_id'] = str(user['_id'])
    emit('profile_updated', user)
    broadcast_contacts()

@socketio.on('get_contacts')
def send_contacts():
    broadcast_contacts()

def broadcast_contacts():
    users = list(users_col.find({}, {"_id": 0, "pin": 0, "sid": 0}))
    socketio.emit('contacts_data', users)

@socketio.on('send_msg')
def handle_msg(data):
    msg_obj = {**data, "timestamp": datetime.datetime.now(), "seen": False}
    chats_col.insert_one(msg_obj)
    target = users_col.find_one({"phone": data['to']})
    if target and target['status'] == 'online':
        emit('new_msg', data, room=target['sid'])

@socketio.on('get_messages')
def get_msgs(data):
    msgs = list(chats_col.find({
        "$or": [
            {"from": data['from'], "to": data['to']},
            {"from": data['to'], "to": data['from']}
        ]
    }, {"_id": 0}).sort("timestamp", 1))
    emit('load_msgs', msgs)

@socketio.on('get_chat_list')
def get_chat_list(data):
    # এটা একটু জটিল কোয়েরি, সংক্ষেপে বোঝানোর জন্য:
    # যাদের সাথে মেসেজ আদান প্রদান হয়েছে তাদের লিস্ট বের করা
    pipeline = [
        {"$match": {"$or": [{"from": data['phone']}, {"to": data['phone']}]}},
        {"$sort": {"timestamp": -1}},
        {"$group": {
            "_id": {"$cond": [{"$eq": ["$from", data['phone']]}, "$to", "$from"]},
            "lastMsg": {"$first": "$message"},
            "type": {"$first": "$type"}
        }}
    ]
    results = list(chats_col.aggregate(pipeline))
    chat_list = []
    for res in results:
        u = users_col.find_one({"phone": res['_id']})
        if u:
            chat_list.append({
                "phone": u['phone'],
                "name": u['name'],
                "avatar": u['avatar'],
                "lastMsg": "📷 Photo" if res['type'] == 'image' else res['lastMsg'][:20]
            })
    emit('chat_list_data', chat_list)

@socketio.on('typing')
def typing(data):
    target = users_col.find_one({"phone": data['to']})
    if target: emit('user_typing', {"from": data['from']}, room=target['sid'])

@socketio.on('call_signal')
def call_signal(data):
    target = users_col.find_one({"phone": data['to']})
    if target: emit('call_signal', data, room=target['sid'])

@socketio.on('disconnect')
def on_disconnect():
    users_col.update_one({"sid": request.sid}, {"$set": {"status": "offline"}})
    broadcast_contacts()

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host='0.0.0.0', port=port)
