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
app.config['SECRET_KEY'] = 'imo-pro-v3-2026-final'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet', max_http_buffer_size=10**7) 

# --- ডাটাবেস কানেকশন ---
MONGO_URI = "mongodb+srv://Demo270:Demo270@cluster0.ls1igsg.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0" 

try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    db = client['imo_pro_v3']
    users_col = db['users']
    chats_col = db['chats']
    calls_col = db['calls'] # কল হিস্ট্রির জন্য নতুন কালেকশন
    client.admin.command('ping')
    print("✅ MongoDB Connected Successfully!")
except Exception as e:
    print(f"❌ DB Error: {e}")

# --- ফ্রন্টএন্ড UI ---
html_content = """
<!DOCTYPE html>
<html lang="bn">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Imo Pro - Final</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <style>
        :root { --main: #2e86de; --bg: #f1f2f6; --white: #ffffff; --grey: #8395a7; --green: #10ac84; --danger: #ff4757; }
        body { font-family: 'Segoe UI', sans-serif; background: var(--bg); margin: 0; display: flex; justify-content: center; height: 100vh; overflow: hidden; }
        .hidden { display: none !important; }
        
        .app-container { width: 100%; max-width: 450px; background: var(--white); display: flex; flex-direction: column; position: relative; box-shadow: 0 0 20px rgba(0,0,0,0.1); }
        
        /* Auth Screen */
        .screen { padding: 30px 20px; text-align: center; height: 100%; overflow-y: auto; box-sizing: border-box; }
        input { width: 100%; padding: 14px; margin: 10px 0; border: 1px solid #ddd; border-radius: 10px; font-size: 16px; outline: none; }
        .btn { width: 100%; padding: 14px; border: none; border-radius: 10px; cursor: pointer; font-weight: bold; font-size: 16px; margin-top: 10px; background: var(--main); color: white; }

        header { background: var(--main); color: white; padding: 15px; display: flex; justify-content: space-between; align-items: center; font-size: 18px; font-weight: bold; }
        
        .tabs { display: flex; background: var(--main); border-bottom: 2px solid rgba(0,0,0,0.1); }
        .tab { flex: 1; padding: 12px; text-align: center; color: rgba(255,255,255,0.7); cursor: pointer; font-weight: bold; font-size: 14px; }
        .tab.active { color: white; border-bottom: 3px solid white; }

        .list-container { flex: 1; overflow-y: auto; }
        .item { display: flex; align-items: center; padding: 12px 15px; border-bottom: 1px solid #f0f0f0; cursor: pointer; position: relative; }
        .avatar { width: 45px; height: 45px; border-radius: 50%; background: #ddd; margin-right: 12px; display: flex; align-items: center; justify-content: center; font-size: 18px; color: #666; object-fit: cover; }
        .item-info { flex: 1; }
        .item-info b { display: block; font-size: 15px; }
        .item-info span { font-size: 12px; color: var(--grey); }
        .online-dot { width: 10px; height: 10px; background: var(--green); border-radius: 50%; border: 2px solid white; position: absolute; left: 48px; top: 48px; }

        /* Chat Window */
        #chatView { position: absolute; top: 0; left: 0; width: 100%; height: 100%; background: #e5ddd5; z-index: 1000; display: flex; flex-direction: column; }
        .chat-msgs { flex: 1; padding: 15px; overflow-y: auto; display: flex; flex-direction: column; gap: 8px; }
        .msg { padding: 8px 12px; border-radius: 12px; max-width: 80%; font-size: 14px; position: relative; box-shadow: 0 1px 1px rgba(0,0,0,0.1); display: flex; flex-direction: column; }
        .msg.sent { background: #dcf8c6; align-self: flex-end; border-bottom-right-radius: 2px; }
        .msg.recv { background: white; align-self: flex-start; border-bottom-left-radius: 2px; }
        .delete-btn { font-size: 10px; color: var(--danger); cursor: pointer; align-self: flex-end; margin-top: 4px; }

        .chat-footer { background: #f0f0f0; padding: 10px; display: flex; align-items: center; gap: 8px; }
        .footer-input { flex: 1; background: white; border-radius: 20px; padding: 5px 15px; display: flex; align-items: center; }
        .footer-input input { border: none; padding: 8px; width: 100%; outline: none; }
        
        .icon-btn { cursor: pointer; font-size: 20px; color: var(--main); user-select: none; }
        .recording { color: var(--danger) !important; animation: pulse 1s infinite; }
        @keyframes pulse { 0% { transform: scale(1); } 50% { transform: scale(1.2); } 100% { transform: scale(1); } }

        /* Call Screen */
        .call-overlay { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: #075e54; z-index: 9999; color: white; display: flex; flex-direction: column; align-items: center; justify-content: center; }
        .video-box { width: 100%; height: 70%; position: relative; background: #000; }
        #remoteVideo { width: 100%; height: 100%; object-fit: cover; }
        #localVideo { width: 90px; height: 130px; position: absolute; bottom: 20px; right: 20px; border: 2px solid white; border-radius: 8px; }
        .call-btns { margin-top: 30px; display: flex; gap: 40px; }
        .call-action-btn { width: 60px; height: 60px; border-radius: 50%; border: none; cursor: pointer; font-size: 24px; color: white; display: flex; align-items: center; justify-content: center; }
    </style>
</head>
<body>

    <audio id="ringtone" src="https://www.soundjay.com/phone/phone-calling-1.mp3" loop></audio>

    <div class="app-container">
        
        <!-- ১. অথ স্ক্রিন -->
        <div id="authScreen" class="screen">
            <h1 style="color: var(--main); font-size: 40px;">imo</h1>
            <p>লগইন অথবা নতুন একাউন্ট খুলুন</p>
            <input type="number" id="authPhone" placeholder="মোবাইল নাম্বার">
            <input type="password" id="authPin" placeholder="৫ ডিজিট পিন">
            <button class="btn" onclick="auth()">চালিয়ে যান</button>
        </div>

        <!-- ২. প্রোফাইল সেটআপ -->
        <div id="profileScreen" class="screen hidden">
            <h2>প্রোফাইল সেটআপ</h2>
            <div id="avatarPreview" class="avatar" style="width: 100px; height: 100px; margin: 0 auto 20px;">👤</div>
            <input type="text" id="setupName" placeholder="আপনার নাম">
            <input type="file" id="avatarFile" accept="image/*" onchange="previewAvatar(event)">
            <button class="btn" onclick="saveProfile()">সম্পন্ন করুন</button>
        </div>

        <!-- ৩. মেইন ড্যাশবোর্ড -->
        <div id="mainDashboard" class="hidden" style="display: flex; flex-direction: column; height: 100%;">
            <header>
                <span>imo</span>
                <span id="displayMyPhone" style="font-size: 12px; font-weight: normal;"></span>
                <span onclick="logout()" style="font-size: 12px; cursor: pointer; background: rgba(0,0,0,0.1); padding: 4px 8px; border-radius: 4px;">Logout</span>
            </header>
            <div class="tabs">
                <div class="tab active" onclick="switchTab('chats', this)">CHATS</div>
                <div class="tab" onclick="switchTab('contacts', this)">CONTACTS</div>
                <div class="tab" onclick="switchTab('calls', this)">CALLS</div>
            </div>
            
            <div id="chatsTab" class="list-container"></div>
            <div id="contactsTab" class="list-container hidden">
                <div style="padding: 10px; display: flex; gap: 10px;">
                    <input type="number" id="searchUser" placeholder="নাম্বার খুঁজুন" style="margin: 0; flex: 1;">
                    <button onclick="addFriend()" style="padding: 0 15px; border-radius: 10px; border: none; background: var(--main); color: white;">Add</button>
                </div>
                <div id="contactList"></div>
            </div>
            <div id="callsTab" class="list-container hidden"></div>
        </div>

        <!-- ৪. চ্যাট উইন্ডো -->
        <div id="chatView" class="hidden">
            <div class="chat-header">
                <span onclick="closeChat()" style="cursor:pointer; font-size: 24px;">←</span>
                <img id="chatAvatar" class="avatar" style="width: 35px; height: 35px; margin: 0;">
                <div style="flex: 1;">
                    <div id="chatName" style="font-weight: bold; font-size: 16px;">নাম</div>
                    <div id="typingStatus" style="font-size: 10px; opacity: 0.8;"></div>
                </div>
                <div style="display: flex; gap: 15px;">
                    <span onclick="startCall('video')" style="cursor:pointer;">📹</span>
                    <span onclick="startCall('audio')" style="cursor:pointer;">📞</span>
                </div>
            </div>
            <div id="chatBox" class="chat-msgs"></div>
            <div class="chat-footer">
                <label for="imgUpload" class="icon-btn">🖼️</label>
                <input type="file" id="imgUpload" hidden accept="image/*" onchange="sendImage(event)">
                <div class="footer-input">
                    <input type="text" id="msgInput" placeholder="মেসেজ লিখুন..." oninput="handleTyping()">
                </div>
                <!-- ভয়েস মেসেজ হোল্ড-টু-রেকর্ড -->
                <span id="voiceBtn" class="icon-btn" 
                      onmousedown="startVoice()" onmouseup="stopVoice()" 
                      ontouchstart="startVoice()" ontouchend="stopVoice()">🎙️</span>
                <span class="icon-btn" onclick="sendText()">➤</span>
            </div>
        </div>

        <!-- ৫. কল ওভারলে -->
        <div id="callOverlay" class="call-overlay hidden">
            <h2 id="callTargetName">বন্ধুর নাম</h2>
            <p id="callStatus">Calling...</p>
            <div id="videoContainer" class="video-box hidden">
                <video id="remoteVideo" autoplay playsinline></video>
                <video id="localVideo" autoplay playsinline muted></video>
            </div>
            <div class="call-btns">
                <button id="btnAccept" class="call-action-btn" style="background: var(--green);" onclick="acceptCall()">📞</button>
                <button class="call-action-btn" style="background: var(--danger);" onclick="endCall()">✖</button>
            </div>
        </div>
    </div>

    <script>
        const socket = io();
        let myData = null, activeChat = null, peerConn, localStream, typingTimeout;
        let mediaRecorder, voiceChunks = [];
        const rtcConfig = { iceServers: [{ urls: 'stun:stun.l.google.com:19302' }] };

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
                document.getElementById('displayMyPhone').innerText = myData.phone;
                if (!data.user.name) document.getElementById('profileScreen').classList.remove('hidden');
                else showDashboard();
            } else alert(data.message);
        });

        function saveProfile() {
            const name = document.getElementById('setupName').value.trim();
            const avatar = document.getElementById('avatarPreview').querySelector('img')?.src || "";
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
            socket.emit('get_contacts', { phone: myData.phone });
            socket.emit('get_chat_list', { phone: myData.phone });
            socket.emit('get_call_history', { phone: myData.phone });
        }

        function switchTab(tab, el) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            el.classList.add('active');
            document.getElementById('chatsTab').classList.toggle('hidden', tab !== 'chats');
            document.getElementById('contactsTab').classList.toggle('hidden', tab !== 'contacts');
            document.getElementById('callsTab').classList.toggle('hidden', tab !== 'calls');
            if(tab === 'calls') socket.emit('get_call_history', { phone: myData.phone });
        }

        function addFriend() {
            const phone = document.getElementById('searchUser').value.trim();
            if(!phone || phone === myData.phone) return alert("সঠিক নম্বর দিন");
            socket.emit('add_friend', { myPhone: myData.phone, friendPhone: phone });
        }

        socket.on('add_friend_res', res => {
            alert(res.message);
            if(res.status === 'success') socket.emit('get_contacts', { phone: myData.phone });
        });

        socket.on('contacts_data', users => {
            const list = document.getElementById('contactList');
            list.innerHTML = "";
            users.forEach(u => {
                list.innerHTML += `<div class="item" onclick="openChat('${u.phone}', '${u.name}', '${u.avatar}')">
                    <div class="avatar" style="background-image:url('${u.avatar || ''}')">${u.avatar ? '' : '👤'}</div>
                    <div class="item-info"><b>${u.name}</b><span>${u.phone}</span></div>
                    ${u.status === 'online' ? '<div class="online-dot"></div>' : ''}
                </div>`;
            });
        });

        socket.on('chat_list_data', chats => {
            const list = document.getElementById('chatsTab');
            list.innerHTML = "";
            chats.forEach(c => {
                list.innerHTML += `<div class="item" onclick="openChat('${c.phone}', '${c.name}', '${c.avatar}')">
                    <img class="avatar" src="${c.avatar || 'https://via.placeholder.com/45?text=👤'}">
                    <div class="item-info"><b>${c.name}</b><span>${c.lastMsg}</span></div>
                </div>`;
            });
        });

        socket.on('call_history_data', calls => {
            const list = document.getElementById('callsTab');
            list.innerHTML = "";
            calls.forEach(c => {
                const isIncoming = c.to === myData.phone;
                list.innerHTML += `<div class="item">
                    <div class="avatar">📞</div>
                    <div class="item-info">
                        <b>${isIncoming ? c.from : c.to}</b>
                        <span>${isIncoming ? 'Incoming' : 'Outgoing'} • ${c.type} • ${c.time}</span>
                    </div>
                </div>`;
            });
        });

        // --- চ্যাট ও ভয়েস লজিক ---
        function openChat(phone, name, avatar) {
            activeChat = { phone, name, avatar };
            document.getElementById('chatView').classList.remove('hidden');
            document.getElementById('chatName').innerText = name;
            document.getElementById('chatAvatar').src = avatar || 'https://via.placeholder.com/35?text=👤';
            document.getElementById('chatBox').innerHTML = "";
            socket.emit('get_messages', { from: myData.phone, to: phone });
        }

        function closeChat() { document.getElementById('chatView').classList.add('hidden'); activeChat = null; }

        function sendText() {
            const text = document.getElementById('msgInput').value.trim();
            if (!text) return;
            const msgData = { from: myData.phone, to: activeChat.phone, message: text, type: 'text' };
            socket.emit('send_msg', msgData);
            appendMessage({...msgData, _id: Date.now()}, 'sent');
            document.getElementById('msgInput').value = "";
        }

        // হোল্ড-টু-রেকর্ড ভয়েস
        async function startVoice() {
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                mediaRecorder = new MediaRecorder(stream);
                mediaRecorder.start();
                voiceChunks = [];
                document.getElementById('voiceBtn').classList.add('recording');
                mediaRecorder.ondataavailable = e => voiceChunks.push(e.data);
                mediaRecorder.onstop = () => {
                    const blob = new Blob(voiceChunks, { type: 'audio/ogg; codecs=opus' });
                    const reader = new FileReader();
                    reader.onload = (e) => {
                        const msgData = { from: myData.phone, to: activeChat.phone, message: e.target.result, type: 'voice' };
                        socket.emit('send_msg', msgData);
                        appendMessage({...msgData, _id: Date.now()}, 'sent');
                    };
                    reader.readAsDataURL(blob);
                };
            } catch(e) { alert("মাইক্রোফোন পারমিশন প্রয়োজন"); }
        }

        function stopVoice() {
            if(mediaRecorder && mediaRecorder.state !== 'inactive') {
                mediaRecorder.stop();
                document.getElementById('voiceBtn').classList.remove('recording');
            }
        }

        function deleteMessage(id) {
            if(confirm("মেসেজটি ডিলিট করতে চান?")) {
                socket.emit('delete_msg', { msgId: id, from: myData.phone });
                const el = document.getElementById(`msg-${id}`);
                if(el) el.remove();
            }
        }

        socket.on('msg_deleted', id => {
            const el = document.getElementById(`msg-${id}`);
            if(el) el.remove();
        });

        function appendMessage(data, side) {
            const box = document.getElementById('chatBox');
            const div = document.createElement('div');
            div.className = `msg ${side}`;
            div.id = `msg-${data._id}`;
            let content = "";
            if (data.type === 'text') content = `<span>${data.message}</span>`;
            else if (data.type === 'image') content = `<img src="${data.message}" style="max-width:200px; border-radius:8px;">`;
            else if (data.type === 'voice') content = `<audio src="${data.message}" controls style="max-width:180px;"></audio>`;
            
            div.innerHTML = `${content} <span class="delete-btn" onclick="deleteMessage('${data._id}')">Delete</span>`;
            box.appendChild(div);
            box.scrollTop = box.scrollHeight;
        }

        // --- কল লজিক ---
        async function startCall(type) {
            document.getElementById('callOverlay').classList.remove('hidden');
            document.getElementById('callTargetName').innerText = activeChat.name;
            if (type === 'video') document.getElementById('videoContainer').classList.remove('hidden');
            localStream = await navigator.mediaDevices.getUserMedia({ video: type === 'video', audio: true });
            document.getElementById('localVideo').srcObject = localStream;
            peerConn = new RTCPeerConnection(rtcConfig);
            localStream.getTracks().forEach(track => peerConn.addTrack(track, localStream));
            peerConn.onicecandidate = e => e.candidate && socket.emit('call_signal', { to: activeChat.phone, from: myData.phone, candidate: e.candidate });
            peerConn.ontrack = e => document.getElementById('remoteVideo').srcObject = e.streams[0];
            const offer = await peerConn.createOffer();
            await peerConn.setLocalDescription(offer);
            socket.emit('call_signal', { to: activeChat.phone, from: myData.phone, offer, type, name: myData.name });
            socket.emit('log_call', { from: myData.phone, to: activeChat.phone, type: type });
        }

        let incomingSignal = null;
        socket.on('call_signal', async data => {
            if (data.offer) {
                incomingSignal = data;
                document.getElementById('callOverlay').classList.remove('hidden');
                document.getElementById('callTargetName').innerText = data.name;
                document.getElementById('btnAccept').classList.remove('hidden');
                document.getElementById('ringtone').play();
            } else if (data.answer) {
                await peerConn.setRemoteDescription(new RTCSessionDescription(data.answer));
            } else if (data.candidate) {
                try { await peerConn.addIceCandidate(new RTCIceCandidate(data.candidate)); } catch(e) {}
            }
        });

        async function acceptCall() {
            document.getElementById('ringtone').pause();
            document.getElementById('btnAccept').classList.add('hidden');
            if (incomingSignal.type === 'video') document.getElementById('videoContainer').classList.remove('hidden');
            localStream = await navigator.mediaDevices.getUserMedia({ video: incomingSignal.type === 'video', audio: true });
            document.getElementById('localVideo').srcObject = localStream;
            peerConn = new RTCPeerConnection(rtcConfig);
            localStream.getTracks().forEach(track => peerConn.addTrack(track, localStream));
            peerConn.onicecandidate = e => e.candidate && socket.emit('call_signal', { to: incomingSignal.from, from: myData.phone, candidate: e.candidate });
            peerConn.ontrack = e => document.getElementById('remoteVideo').srcObject = e.streams[0];
            await peerConn.setRemoteDescription(new RTCSessionDescription(incomingSignal.offer));
            const answer = await peerConn.createAnswer();
            await peerConn.setLocalDescription(answer);
            socket.emit('call_signal', { to: incomingSignal.from, from: myData.phone, answer });
        }

        function endCall() { location.reload(); }
        function logout() { localStorage.removeItem('imo_v3_session'); location.reload(); }
        function previewAvatar(e) {
            const reader = new FileReader();
            reader.onload = (ev) => document.getElementById('avatarPreview').innerHTML = `<img src="${ev.target.result}" style="width:100%;height:100%;border-radius:50%;">`;
            reader.readAsDataURL(e.target.files[0]);
        }
        function handleTyping() { socket.emit('typing', { from: myData.phone, to: activeChat.phone }); }
        socket.on('user_typing', data => {
            if (activeChat && activeChat.phone === data.from) {
                document.getElementById('typingStatus').innerText = "typing...";
                clearTimeout(typingTimeout);
                typingTimeout = setTimeout(() => document.getElementById('typingStatus').innerText = "", 2000);
            }
        });
        socket.on('load_msgs', msgs => msgs.forEach(m => appendMessage(m, m.from === myData.phone ? 'sent' : 'recv')));
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
    phone, pin = str(data.get('phone')), str(data.get('pin'))
    user = users_col.find_one({"phone": phone})
    if user:
        if user['pin'] == pin:
            users_col.update_one({"phone": phone}, {"$set": {"status": "online", "sid": request.sid}})
            user['_id'] = str(user['_id'])
            emit('auth_response', {"status": "success", "user": user})
        else: 
            emit('auth_response', {"status": "error", "message": "ভুল পিন! অন্য পিন চেষ্টা করুন।"})
    else:
        # নতুন একাউন্ট তৈরি
        new_user = {"phone": phone, "pin": pin, "name": "", "avatar": "", "status": "online", "sid": request.sid, "contacts": []}
        users_col.insert_one(new_user)
        new_user['_id'] = str(new_user['_id'])
        emit('auth_response', {"status": "success", "user": new_user})

@socketio.on('auto_login')
def auto_login(data):
    user = users_col.find_one({"phone": data['phone'], "pin": data['pin']})
    if user:
        users_col.update_one({"phone": data['phone']}, {"$set": {"status": "online", "sid": request.sid}})
        user['_id'] = str(user['_id'])
        emit('auth_response', {"status": "success", "user": user})

@socketio.on('update_profile')
def update_profile(data):
    users_col.update_one({"phone": data['phone']}, {"$set": {"name": data['name'], "avatar": data['avatar']}})
    user = users_col.find_one({"phone": data['phone']})
    user['_id'] = str(user['_id'])
    emit('profile_updated', user)

@socketio.on('add_friend')
def add_friend(data):
    me, friend = data['myPhone'], data['friendPhone']
    target = users_col.find_one({"phone": friend})
    if not target:
        emit('add_friend_res', {"status": "error", "message": "নম্বরটি সিস্টেমে নেই!"})
    else:
        users_col.update_one({"phone": me}, {"$addToSet": {"contacts": friend}})
        users_col.update_one({"phone": friend}, {"$addToSet": {"contacts": me}})
        emit('add_friend_res', {"status": "success", "message": "সফলভাবে বন্ধু যুক্ত হয়েছে!"})

@socketio.on('delete_msg')
def delete_msg(data):
    msg_id = data.get('msgId')
    # সিকিউরিটির জন্য চেক করা যেতে পারে যে ইউজার নিজের মেসেজ ডিলিট করছে কিনা
    chats_col.delete_one({"_id": ObjectId(msg_id)}) if len(str(msg_id)) == 24 else chats_col.delete_one({"_id": msg_id})
    socketio.emit('msg_deleted', msg_id)

@socketio.on('log_call')
def log_call(data):
    call_log = {
        "from": data['from'],
        "to": data['to'],
        "type": data['type'],
        "time": datetime.datetime.now().strftime("%d %b, %H:%M")
    }
    calls_col.insert_one(call_log)

@socketio.on('get_call_history')
def get_calls(data):
    calls = list(calls_col.find({"$or": [{"from": data['phone']}, {"to": data['phone']}]}).sort("_id", -1).limit(20))
    for c in calls: c['_id'] = str(c['_id'])
    emit('call_history_data', calls)

@socketio.on('send_msg')
def handle_msg(data):
    msg_obj = {**data, "timestamp": datetime.datetime.now()}
    result = chats_col.insert_one(msg_obj)
    data['_id'] = str(result.inserted_id)
    target = users_col.find_one({"phone": data['to']})
    if target and target['status'] == 'online':
        emit('new_msg', data, room=target['sid'])

@socketio.on('get_messages')
def get_msgs(data):
    msgs = list(chats_col.find({
        "$or": [{"from": data['from'], "to": data['to']}, {"from": data['to'], "to": data['from']}]
    }).sort("timestamp", 1))
    for m in msgs: m['_id'] = str(m['_id'])
    emit('load_msgs', msgs)

@socketio.on('get_chat_list')
def get_chat_list(data):
    pipeline = [
        {"$match": {"$or": [{"from": data['phone']}, {"to": data['phone']}]}},
        {"$sort": {"timestamp": -1}},
        {"$group": {"_id": {"$cond": [{"$eq": ["$from", data['phone']]}, "$to", "$from"]}, "lastMsg": {"$first": "$message"}}}
    ]
    results = list(chats_col.aggregate(pipeline))
    chat_list = []
    for res in results:
        u = users_col.find_one({"phone": res['_id']})
        if u: chat_list.append({"phone": u['phone'], "name": u['name'], "avatar": u['avatar'], "lastMsg": res['lastMsg'][:20]})
    emit('chat_list_data', chat_list)

@socketio.on('call_signal')
def call_signal(data):
    target = users_col.find_one({"phone": data['to']})
    if target: emit('call_signal', data, room=target['sid'])

@socketio.on('disconnect')
def on_disconnect():
    users_col.update_one({"sid": request.sid}, {"$set": {"status": "offline"}})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host='0.0.0.0', port=port)
