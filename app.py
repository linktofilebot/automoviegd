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
app.config['SECRET_KEY'] = 'imo-pro-premium-2026'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet', max_http_buffer_size=10**7) 

# --- ডাটাবেস কানেকশন ---
MONGO_URI = "mongodb+srv://Demo270:Demo270@cluster0.ls1igsg.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0" 

try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    db = client['imo_pro_v3']
    users_col = db['users']
    chats_col = db['chats']
    calls_col = db['calls']
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
    <title>Imo Pro Premium</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <style>
        :root { --main: #0984e3; --dark: #2d3436; --bg: #f5f6fa; --white: #ffffff; --green: #00b894; --danger: #d63031; --shadow: 0 4px 15px rgba(0,0,0,0.1); }
        body { font-family: 'Segoe UI', sans-serif; background: #dfe6e9; margin: 0; display: flex; justify-content: center; height: 100vh; overflow: hidden; }
        .hidden { display: none !important; }
        
        .app-container { width: 100%; max-width: 450px; background: var(--white); display: flex; flex-direction: column; position: relative; box-shadow: 0 0 30px rgba(0,0,0,0.2); }
        
        /* Premium Auth */
        .screen { padding: 40px 20px; text-align: center; height: 100%; overflow-y: auto; box-sizing: border-box; }
        .screen h1 { color: var(--main); font-size: 50px; margin-bottom: 5px; font-weight: 800; }
        input { width: 100%; padding: 15px; margin: 12px 0; border: 2px solid #eee; border-radius: 12px; font-size: 16px; outline: none; transition: 0.3s; }
        input:focus { border-color: var(--main); }
        .btn { width: 100%; padding: 16px; border: none; border-radius: 12px; cursor: pointer; font-weight: bold; font-size: 16px; background: var(--main); color: white; box-shadow: var(--shadow); }

        header { background: var(--main); color: white; padding: 15px 20px; display: flex; justify-content: space-between; align-items: center; box-shadow: var(--shadow); z-index: 10; }
        
        .tabs { display: flex; background: var(--main); }
        .tab { flex: 1; padding: 15px; text-align: center; color: rgba(255,255,255,0.7); cursor: pointer; font-weight: bold; font-size: 13px; transition: 0.3s; }
        .tab.active { color: white; border-bottom: 4px solid white; background: rgba(255,255,255,0.1); }

        .list-container { flex: 1; overflow-y: auto; background: var(--bg); }
        .item { display: flex; align-items: center; padding: 15px; background: var(--white); margin-bottom: 1px; cursor: pointer; transition: 0.2s; }
        .item:hover { background: #f1f2f6; }
        .avatar { width: 50px; height: 50px; border-radius: 50%; background: #dfe6e9; margin-right: 15px; display: flex; align-items: center; justify-content: center; font-size: 20px; font-weight: bold; color: var(--main); background-size: cover; background-position: center; border: 2px solid #eee; }
        .item-info { flex: 1; }
        .item-info b { font-size: 16px; color: var(--dark); }
        .item-info span { font-size: 13px; color: #636e72; }
        
        /* Premium Profile Overlay */
        .profile-overlay { position: absolute; top: 0; left: 0; width: 100%; height: 100%; background: var(--bg); z-index: 2000; display: flex; flex-direction: column; align-items: center; padding-top: 50px; animation: slideIn 0.3s ease-out; }
        @keyframes slideIn { from { transform: translateY(100%); } to { transform: translateY(0); } }
        .profile-card { width: 85%; background: white; border-radius: 20px; padding: 30px; text-align: center; box-shadow: var(--shadow); }
        .profile-avatar { width: 120px; height: 120px; border-radius: 50%; border: 5px solid var(--main); margin-bottom: 20px; object-fit: cover; }

        /* Chat UI */
        #chatView { position: absolute; top: 0; left: 0; width: 100%; height: 100%; background: #f0f2f5; z-index: 1000; display: flex; flex-direction: column; }
        .chat-header { background: var(--main); color: white; padding: 10px 15px; display: flex; align-items: center; gap: 12px; }
        .chat-msgs { flex: 1; padding: 15px; overflow-y: auto; display: flex; flex-direction: column; gap: 10px; }
        .msg { padding: 10px 15px; border-radius: 18px; max-width: 75%; font-size: 14px; position: relative; box-shadow: 0 2px 5px rgba(0,0,0,0.05); }
        .msg.sent { background: var(--main); color: white; align-self: flex-end; border-bottom-right-radius: 2px; }
        .msg.recv { background: white; color: var(--dark); align-self: flex-start; border-bottom-left-radius: 2px; }
        .delete-btn { font-size: 9px; opacity: 0.7; cursor: pointer; margin-top: 5px; text-align: right; text-decoration: underline; }

        .chat-footer { background: white; padding: 12px; display: flex; align-items: center; gap: 10px; border-top: 1px solid #eee; }
        .footer-input { flex: 1; background: #f1f2f6; border-radius: 30px; padding: 5px 15px; }
        .footer-input input { border: none; padding: 10px; width: 100%; background: transparent; }
        
        .icon-btn { cursor: pointer; font-size: 24px; color: var(--main); }
        .recording { color: var(--danger) !important; animation: pulse 1s infinite; }

        /* Call Screen */
        .call-overlay { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: #1e272e; z-index: 9999; color: white; display: flex; flex-direction: column; align-items: center; justify-content: center; }
        .video-box { width: 100%; height: 80%; position: relative; }
        #remoteVideo { width: 100%; height: 100%; object-fit: cover; }
        #localVideo { width: 100px; height: 150px; position: absolute; bottom: 20px; right: 20px; border: 2px solid white; border-radius: 12px; }
    </style>
</head>
<body>

    <audio id="ringtone" src="https://www.soundjay.com/phone/phone-calling-1.mp3" loop></audio>

    <div class="app-container">
        
        <!-- ১. অথ স্ক্রিন -->
        <div id="authScreen" class="screen">
            <h1 onclick="location.reload()">imo</h1>
            <p style="color: #636e72;">প্রিমিয়াম কোয়ালিটি চ্যাট ও কলিং</p>
            <input type="number" id="authPhone" placeholder="মোবাইল নাম্বার">
            <input type="password" id="authPin" placeholder="৫ ডিজিট পিন">
            <button class="btn" onclick="auth()">শুরু করুন</button>
        </div>

        <!-- ২. প্রোফাইল সেটআপ -->
        <div id="profileScreen" class="screen hidden">
            <h2>আপনার প্রোফাইল সাজান</h2>
            <div id="avatarPreview" class="avatar" style="width: 120px; height: 120px; margin: 0 auto 20px; font-size: 40px;">👤</div>
            <input type="text" id="setupName" placeholder="আপনার নাম">
            <input type="file" id="avatarFile" accept="image/*" onchange="previewAvatar(event)">
            <button class="btn" onclick="saveProfile()">সম্পন্ন করুন</button>
        </div>

        <!-- ৩. মেইন ড্যাশবোর্ড -->
        <div id="mainDashboard" class="hidden" style="display: flex; flex-direction: column; height: 100%;">
            <header>
                <div style="display: flex; align-items: center; gap: 10px;" onclick="viewMyProfile()">
                    <div id="headerAvatar" class="avatar" style="width:35px; height:35px; margin:0; font-size: 14px;">👤</div>
                    <span>imo Pro</span>
                </div>
                <span onclick="logout()" style="font-size: 11px; opacity: 0.8;">LOGOUT</span>
            </header>
            <div class="tabs">
                <div class="tab active" onclick="switchTab('chats', this)">CHATS</div>
                <div class="tab" onclick="switchTab('contacts', this)">CONTACTS</div>
                <div class="tab" onclick="switchTab('calls', this)">CALLS</div>
            </div>
            
            <div id="chatsTab" class="list-container"></div>
            <div id="contactsTab" class="list-container hidden">
                <div style="padding: 15px; display: flex; gap: 10px;">
                    <input type="number" id="searchUser" placeholder="বন্ধুর নাম্বার লিখুন" style="margin: 0; flex: 1; padding: 12px;">
                    <button onclick="addFriend()" style="width: 60px; border-radius: 12px; border: none; background: var(--main); color: white;">ADD</button>
                </div>
                <div id="contactList"></div>
            </div>
            <div id="callsTab" class="list-container hidden"></div>
        </div>

        <!-- ৪. চ্যাট উইন্ডো -->
        <div id="chatView" class="hidden">
            <div class="chat-header">
                <span onclick="closeChat()" style="cursor:pointer; font-size: 26px;">←</span>
                <img id="chatAvatar" class="avatar" style="width: 38px; height: 38px; margin: 0;" onclick="viewFriendProfile()">
                <div style="flex: 1;" onclick="viewFriendProfile()">
                    <div id="chatName" style="font-weight: bold; font-size: 16px;">বন্ধুর নাম</div>
                    <div id="typingStatus" style="font-size: 10px; opacity: 0.8;"></div>
                </div>
                <div style="display: flex; gap: 18px;">
                    <span onclick="startCall('video')" style="cursor:pointer; font-size: 20px;">📹</span>
                    <span onclick="startCall('audio')" style="cursor:pointer; font-size: 20px;">📞</span>
                </div>
            </div>
            <div id="chatBox" class="chat-msgs"></div>
            <div class="chat-footer">
                <label for="imgUpload" class="icon-btn">🖼️</label>
                <input type="file" id="imgUpload" hidden accept="image/*" onchange="sendImage(event)">
                <div class="footer-input">
                    <input type="text" id="msgInput" placeholder="লিখুন..." oninput="handleTyping()">
                </div>
                <span id="voiceBtn" class="icon-btn" onmousedown="startVoice()" onmouseup="stopVoice()" ontouchstart="startVoice()" ontouchend="stopVoice()">🎙️</span>
                <span class="icon-btn" onclick="sendText()">➤</span>
            </div>
        </div>

        <!-- ৫. প্রোফাইল ওভারলে (Premium) -->
        <div id="profileOverlay" class="profile-overlay hidden">
            <span onclick="closeProfile()" style="position: absolute; top: 20px; left: 20px; font-size: 30px; cursor: pointer;">←</span>
            <div class="profile-card">
                <img id="pOverlayAv" src="" class="profile-avatar">
                <h2 id="pOverlayName">ইউজার নেম</h2>
                <p id="pOverlayPhone" style="color: var(--grey);"></p>
                <div id="pOverlayStatus" style="margin-top: 10px; font-weight: bold;"></div>
                <div id="pActions" style="margin-top: 20px; display: flex; gap: 10px; justify-content: center;">
                    <!-- Actions will be injected -->
                </div>
            </div>
        </div>

        <!-- ৬. কল ওভারলে -->
        <div id="callOverlay" class="call-overlay hidden">
            <h2 id="callTargetName">বন্ধুর নাম</h2>
            <p id="callStatus">Connecting...</p>
            <div id="videoContainer" class="video-box hidden">
                <video id="remoteVideo" autoplay playsinline></video>
                <video id="localVideo" autoplay playsinline muted></video>
            </div>
            <div class="call-btns">
                <button id="btnAccept" class="btn" style="background: var(--green); width: 80px; border-radius: 50%; height: 80px;" onclick="acceptCall()">📞</button>
                <button class="btn" style="background: var(--danger); width: 80px; border-radius: 50%; height: 80px;" onclick="endCall()">✖</button>
            </div>
        </div>

    </div>

    <script>
        const socket = io();
        let myData = null, activeChat = null, peerConn, localStream, typingTimeout;
        let mediaRecorder, voiceChunks = [];
        const rtcConfig = { iceServers: [{ urls: 'stun:stun.l.google.com:19302' }] };

        // সেশন চেক
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
                if (myData.avatar) {
                    document.getElementById('headerAvatar').style.backgroundImage = `url('${myData.avatar}')`;
                    document.getElementById('headerAvatar').innerText = '';
                }
                if (!myData.name) document.getElementById('profileScreen').classList.remove('hidden');
                else showDashboard();
            } else alert(data.message);
        });

        function showDashboard() {
            document.getElementById('mainDashboard').classList.remove('hidden');
            socket.emit('get_contacts', { phone: myData.phone });
            socket.emit('get_chat_list', { phone: myData.phone });
        }

        function switchTab(tab, el) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            el.classList.add('active');
            document.getElementById('chatsTab').classList.toggle('hidden', tab !== 'chats');
            document.getElementById('contactsTab').classList.toggle('hidden', tab !== 'contacts');
            document.getElementById('callsTab').classList.toggle('hidden', tab !== 'calls');
            if(tab === 'calls') socket.emit('get_call_history', { phone: myData.phone });
        }

        // --- প্রোফাইল ভিউ লজিক ---
        function viewMyProfile() {
            renderProfile(myData);
        }

        function viewFriendProfile() {
            if(activeChat) socket.emit('get_user_profile', { phone: activeChat.phone });
        }

        socket.on('user_profile_data', user => {
            renderProfile(user);
        });

        function renderProfile(user) {
            document.getElementById('profileOverlay').classList.remove('hidden');
            document.getElementById('pOverlayName').innerText = user.name || 'No Name';
            document.getElementById('pOverlayPhone').innerText = user.phone;
            document.getElementById('pOverlayAv').src = user.avatar || 'https://via.placeholder.com/150?text=👤';
            document.getElementById('pOverlayStatus').innerText = user.status === 'online' ? '● Online' : '○ Offline';
            document.getElementById('pOverlayStatus').style.color = user.status === 'online' ? 'var(--green)' : 'var(--grey)';
            
            const actionBox = document.getElementById('pActions');
            actionBox.innerHTML = '';
            if(user.phone !== myData.phone) {
                actionBox.innerHTML = `<button class="btn" style="width: auto; padding: 10px 20px;" onclick="closeProfile(); openChat('${user.phone}', '${user.name}', '${user.avatar}')">Message</button>`;
            }
        }

        function closeProfile() { document.getElementById('profileOverlay').classList.add('hidden'); }

        // --- চ্যাট ও ভয়েস ---
        function openChat(phone, name, avatar) {
            activeChat = { phone, name, avatar };
            document.getElementById('chatView').classList.remove('hidden');
            document.getElementById('chatName').innerText = name;
            document.getElementById('chatAvatar').src = avatar || 'https://via.placeholder.com/35?text=👤';
            document.getElementById('chatBox').innerHTML = "";
            socket.emit('get_messages', { from: myData.phone, to: phone });
        }

        function closeChat() { document.getElementById('chatView').classList.add('hidden'); activeChat = null; }

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
            } catch(e) { alert("মাইক্রোফোন এক্সেস দিন"); }
        }

        function stopVoice() {
            if(mediaRecorder && mediaRecorder.state !== 'inactive') {
                mediaRecorder.stop();
                document.getElementById('voiceBtn').classList.remove('recording');
            }
        }

        function appendMessage(data, side) {
            const box = document.getElementById('chatBox');
            const div = document.createElement('div');
            div.className = `msg ${side}`;
            div.id = `msg-${data._id}`;
            let content = "";
            if (data.type === 'text') content = `<span>${data.message}</span>`;
            else if (data.type === 'image') content = `<img src="${data.message}" style="max-width:100%; border-radius:12px;">`;
            else if (data.type === 'voice') content = `<audio src="${data.message}" controls style="width:100%;"></audio>`;
            
            div.innerHTML = `${content} <div class="delete-btn" onclick="deleteMsg('${data._id}')">Delete</div>`;
            box.appendChild(div);
            box.scrollTop = box.scrollHeight;
        }

        function deleteMsg(id) {
            if(confirm("মেসেজটি ডিলিট করতে চান?")) {
                socket.emit('delete_msg', { msgId: id });
                document.getElementById(`msg-${id}`).remove();
            }
        }

        // --- কল হ্যান্ডলিং (No Reload Fix) ---
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

        function endCall() {
            if(localStream) localStream.getTracks().forEach(track => track.stop());
            if(peerConn) peerConn.close();
            document.getElementById('callOverlay').classList.add('hidden');
            document.getElementById('videoContainer').classList.add('hidden');
            document.getElementById('ringtone').pause();
            socket.emit('get_chat_list', { phone: myData.phone });
        }

        // --- অন্যান্য ইভেন্ট ---
        socket.on('contacts_data', users => {
            const list = document.getElementById('contactList');
            list.innerHTML = "";
            users.forEach(u => {
                const avatar = u.avatar ? `style="background-image:url('${u.avatar}')"` : '';
                list.innerHTML += `<div class="item" onclick="openChat('${u.phone}', '${u.name}', '${u.avatar}')">
                    <div class="avatar" ${avatar}>${u.avatar ? '' : (u.name[0] || '👤')}</div>
                    <div class="item-info"><b>${u.name || u.phone}</b><span>${u.phone}</span></div>
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
                const incoming = c.to === myData.phone;
                list.innerHTML += `<div class="item">
                    <div class="avatar">📞</div>
                    <div class="item-info">
                        <b>${incoming ? c.from : c.to}</b>
                        <span>${incoming ? 'Incoming' : 'Outgoing'} • ${c.type} • ${c.time}</span>
                    </div>
                </div>`;
            });
        });

        socket.on('new_msg', d => {
            if (activeChat && activeChat.phone === d.from) appendMessage(d, 'recv');
            else socket.emit('get_chat_list', { phone: myData.phone });
        });

        socket.on('load_msgs', msgs => msgs.forEach(m => appendMessage(m, m.from === myData.phone ? 'sent' : 'recv')));
        
        function previewAvatar(e) {
            const reader = new FileReader();
            reader.onload = (ev) => document.getElementById('avatarPreview').innerHTML = `<img src="${ev.target.result}" style="width:100%;height:100%;border-radius:50%;">`;
            reader.readAsDataURL(e.target.files[0]);
        }
        function saveProfile() {
            const name = document.getElementById('setupName').value.trim();
            const avatar = document.getElementById('avatarPreview').querySelector('img')?.src || "";
            if (!name) return alert("নাম লিখুন");
            socket.emit('update_profile', { phone: myData.phone, name, avatar });
        }
        function logout() { localStorage.clear(); location.reload(); }
        function addFriend() {
            const p = document.getElementById('searchUser').value.trim();
            if(p) socket.emit('add_friend', { myPhone: myData.phone, friendPhone: p });
        }
        function sendImage(e) {
            const reader = new FileReader();
            reader.onload = (ev) => {
                const msgData = { from: myData.phone, to: activeChat.phone, message: ev.target.result, type: 'image' };
                socket.emit('send_msg', msgData);
                appendMessage({...msgData, _id: Date.now()}, 'sent');
            };
            reader.readAsDataURL(e.target.files[0]);
        }
        function sendText() {
            const text = document.getElementById('msgInput').value.trim();
            if (!text) return;
            const msgData = { from: myData.phone, to: activeChat.phone, message: text, type: 'text' };
            socket.emit('send_msg', msgData);
            appendMessage({...msgData, _id: Date.now()}, 'sent');
            document.getElementById('msgInput').value = "";
        }
        function handleTyping() { socket.emit('typing', { from: myData.phone, to: activeChat.phone }); }
        socket.on('user_typing', d => {
            if (activeChat && activeChat.phone === d.from) {
                document.getElementById('typingStatus').innerText = "typing...";
                clearTimeout(typingTimeout);
                typingTimeout = setTimeout(() => document.getElementById('typingStatus').innerText = "", 2000);
            }
        });

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
        else: emit('auth_response', {"status": "error", "message": "ভুল পিন!"})
    else:
        new_user = {"phone": phone, "pin": pin, "name": "", "avatar": "", "status": "online", "sid": request.sid, "contacts": []}
        users_col.insert_one(new_user)
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

@socketio.on('get_user_profile')
def get_user_profile(data):
    user = users_col.find_one({"phone": data['phone']}, {"pin": 0, "sid": 0, "contacts": 0})
    if user:
        user['_id'] = str(user['_id'])
        emit('user_profile_data', user)

@socketio.on('add_friend')
def add_friend(data):
    me, friend = data['myPhone'], data['friendPhone']
    target = users_col.find_one({"phone": friend})
    if target:
        users_col.update_one({"phone": me}, {"$addToSet": {"contacts": friend}})
        users_col.update_one({"phone": friend}, {"$addToSet": {"contacts": me}})
        emit('add_friend_res', {"status": "success", "message": "বন্ধু যুক্ত হয়েছে!"})
    else:
        emit('add_friend_res', {"status": "error", "message": "নম্বরটি সিস্টেমে নেই!"})

@socketio.on('get_contacts')
def get_contacts(data):
    user = users_col.find_one({"phone": data['phone']})
    if user and "contacts" in user:
        contacts = list(users_col.find({"phone": {"$in": user['contacts']}}, {"_id": 0, "pin": 0, "sid": 0}))
        emit('contacts_data', contacts)

@socketio.on('send_msg')
def handle_msg(data):
    msg_obj = {**data, "timestamp": datetime.datetime.now()}
    result = chats_col.insert_one(msg_obj)
    data['_id'] = str(result.inserted_id)
    target = users_col.find_one({"phone": data['to']})
    if target and target['status'] == 'online':
        emit('new_msg', data, room=target['sid'])

@socketio.on('delete_msg')
def delete_msg(data):
    msg_id = data.get('msgId')
    try: chats_col.delete_one({"_id": ObjectId(msg_id)})
    except: chats_col.delete_one({"_id": msg_id})

@socketio.on('log_call')
def log_call(data):
    call_log = {"from": data['from'], "to": data['to'], "type": data['type'], "time": datetime.datetime.now().strftime("%d %b, %H:%M")}
    calls_col.insert_one(call_log)

@socketio.on('get_call_history')
def get_calls(data):
    calls = list(calls_col.find({"$or": [{"from": data['phone']}, {"to": data['phone']}]}).sort("_id", -1).limit(20))
    for c in calls: c['_id'] = str(c['_id'])
    emit('call_history_data', calls)

@socketio.on('get_messages')
def get_msgs(data):
    msgs = list(chats_col.find({"$or": [{"from": data['from'], "to": data['to']}, {"from": data['to'], "to": data['from']}]}).sort("timestamp", 1))
    for m in msgs: m['_id'] = str(m['_id'])
    emit('load_msgs', msgs)

@socketio.on('get_chat_list')
def get_chat_list(data):
    pipeline = [{"$match": {"$or": [{"from": data['phone']}, {"to": data['phone']}]}}, {"$sort": {"timestamp": -1}}, {"$group": {"_id": {"$cond": [{"$eq": ["$from", data['phone']]}, "$to", "$from"]}, "lastMsg": {"$first": "$message"}}}]
    results = list(chats_col.aggregate(pipeline))
    chat_list = []
    for res in results:
        u = users_col.find_one({"phone": res['_id']})
        if u: chat_list.append({"phone": u['phone'], "name": u['name'] or u['phone'], "avatar": u['avatar'], "lastMsg": res['lastMsg'][:20]})
    emit('chat_list_data', chat_list)

@socketio.on('call_signal')
def call_signal(data):
    target = users_col.find_one({"phone": data['to']})
    if target: emit('call_signal', data, room=target['sid'])

@socketio.on('typing')
def typing(data):
    target = users_col.find_one({"phone": data['to']})
    if target: emit('user_typing', {"from": data['from']}, room=target['sid'])

@socketio.on('disconnect')
def on_disconnect():
    users_col.update_one({"sid": request.sid}, {"$set": {"status": "offline"}})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host='0.0.0.0', port=port)
