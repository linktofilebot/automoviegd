# ১. সার্ভার কনফিগারেশন (Monkey Patching)
import eventlet
eventlet.monkey_patch()

import os
import datetime
from flask import Flask, render_template_string, request
from flask_socketio import SocketIO, emit
from pymongo import MongoClient

# --- ফ্লাস্ক অ্যাপ সেটআপ ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'imo-secure-key-2026'
# async_mode='eventlet' রিয়েল টাইম চ্যাটের জন্য সবচেয়ে ভালো
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# --- মোঙ্গোডিবি (MongoDB) কানেকশন ---
# এখানে আপনার ডাটাবেস ইউআরআই দেওয়া আছে
MONGO_URI = "mongodb+srv://Demo270:Demo270@cluster0.ls1igsg.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0" 

try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    db = client['imo_clone_db']
    users_collection = db['users']
    messages_collection = db['messages']
    # কানেকশন চেক
    client.admin.command('ping')
    print("✅ MongoDB কানেক্ট হয়েছে!")
except Exception as e:
    print(f"❌ ডাটাবেস এরর: {e}")

# --- ইউজার ইন্টারফেস (Front-end) ---
html_template = """
<!DOCTYPE html>
<html lang="bn">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Imo Messenger - Call & Chat</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <style>
        :root { --imo-blue: #0088cc; --imo-bg: #e6ebee; --white: #ffffff; }
        body { font-family: 'Segoe UI', sans-serif; background: var(--imo-bg); margin: 0; display: flex; justify-content: center; height: 100vh; overflow: hidden; }
        
        .hidden { display: none !important; }
        .app-box { width: 100%; max-width: 450px; background: white; display: flex; flex-direction: column; position: relative; box-shadow: 0 0 15px rgba(0,0,0,0.2); }
        
        /* Auth Screen */
        .auth-card { padding: 40px 20px; text-align: center; }
        input { width: 90%; padding: 12px; margin: 10px 0; border: 1px solid #ccc; border-radius: 8px; font-size: 16px; }
        .btn { width: 90%; padding: 12px; border: none; border-radius: 8px; cursor: pointer; font-weight: bold; font-size: 16px; margin-top: 10px; transition: 0.3s; }
        .btn-blue { background: var(--imo-blue); color: white; }
        
        /* Header */
        header { background: var(--imo-blue); color: white; padding: 15px; display: flex; justify-content: space-between; align-items: center; }
        
        /* Chat List */
        #contactList { flex: 1; overflow-y: auto; }
        .contact { padding: 15px; border-bottom: 1px solid #f0f0f0; display: flex; align-items: center; cursor: pointer; transition: 0.2s; }
        .contact:hover { background: #f9f9f9; }
        .avatar { width: 45px; height: 45px; background: #ddd; border-radius: 50%; margin-right: 12px; display: flex; align-items: center; justify-content: center; font-weight: bold; color: #555; }
        .status-on { color: #2ecc71; font-size: 12px; }

        /* Chat Window */
        #chatView { position: absolute; top: 0; left: 0; width: 100%; height: 100%; background: #f4f7f9; z-index: 100; display: flex; flex-direction: column; }
        .chat-msgs { flex: 1; padding: 15px; overflow-y: auto; display: flex; flex-direction: column; }
        .m { margin: 5px 0; padding: 10px 14px; border-radius: 12px; max-width: 75%; font-size: 14px; word-wrap: break-word; }
        .sent { background: #d1f2ff; align-self: flex-end; border-bottom-right-radius: 2px; }
        .recv { background: white; align-self: flex-start; border-bottom-left-radius: 2px; box-shadow: 0 1px 2px rgba(0,0,0,0.1); }
        
        .chat-footer { padding: 10px; display: flex; background: white; gap: 8px; }
        .chat-footer input { margin: 0; border-radius: 20px; }
        
        /* Call Screens */
        .call-ui { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: #1c1e21; z-index: 1000; color: white; display: flex; flex-direction: column; align-items: center; justify-content: center; }
        .video-container { width: 90%; height: 60%; position: relative; }
        video { width: 100%; height: 100%; object-fit: cover; border-radius: 10px; background: #000; }
        #localVideo { width: 100px; height: 140px; position: absolute; bottom: 20px; right: 20px; border: 2px solid white; z-index: 1001; }
        .call-btns { margin-top: 30px; display: flex; gap: 20px; }
        .btn-hangup { background: #ff4757; border-radius: 50%; width: 60px; height: 60px; color: white; border: none; font-size: 24px; cursor: pointer; }
        
        .ring-pop { position: fixed; top: 20px; left: 50%; transform: translateX(-50%); width: 90%; max-width: 400px; background: var(--imo-blue); color: white; padding: 15px; border-radius: 12px; z-index: 1100; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 5px 15px rgba(0,0,0,0.3); }
    </style>
</head>
<body>

    <!-- রিংটোন অডিও -->
    <audio id="callRing" src="https://assets.mixkit.co/active_storage/sfx/1359/1359-preview.mp3" loop></audio>

    <div class="app-box">
        
        <!-- ১. রেজিস্ট্রেশন ও লগইন -->
        <div id="authScreen" class="auth-card">
            <h1 style="color: var(--imo-blue);">Imo Lite</h1>
            <p>আপনার ফোন নম্বর দিয়ে শুরু করুন</p>
            <input type="number" id="phoneInput" placeholder="মোবাইল নাম্বার">
            <input type="password" id="pinInput" placeholder="৫ ডিজিটের পিন">
            <button class="btn btn-blue" onclick="handleAuth()">লগইন / রেজিস্ট্রেশন</button>
            <p style="font-size: 12px; color: #777; margin-top: 20px;">একবার লগইন করলে এটি স্থায়ীভাবে থাকবে।</p>
        </div>

        <!-- ২. মেইন কন্টাক্ট লিস্ট -->
        <div id="mainScreen" class="hidden" style="height: 100%; display: flex; flex-direction: column;">
            <header>
                <span>Imo</span>
                <b id="myIdDisplay"></b>
                <button onclick="logout()" style="background:none; border:1px solid white; color:white; font-size:10px; cursor:pointer;">Logout</button>
            </header>
            
            <div style="padding: 10px;">
                <input type="number" id="targetInput" placeholder="বন্ধুর নাম্বার লিখুন..." style="width: 100%; margin: 0; box-sizing: border-box;">
                <button class="btn btn-blue" style="width: 100%; padding: 8px;" onclick="startNewChat()">চ্যাট শুরু করুন</button>
            </div>

            <div id="contactList">
                <!-- কন্টাক্টরা এখানে দেখা যাবে -->
            </div>
        </div>

        <!-- ৩. চ্যাট উইন্ডো -->
        <div id="chatView" class="hidden">
            <header>
                <button onclick="closeChat()" style="background:none; border:none; color:white; font-size:20px; cursor:pointer;">←</button>
                <span id="chatTitle">নাম্বার</span>
                <div style="display:flex; gap:15px;">
                    <button onclick="makeCall('video')" style="background:none; border:none; font-size:20px; cursor:pointer;">📹</button>
                    <button onclick="makeCall('audio')" style="background:none; border:none; font-size:20px; cursor:pointer;">📞</button>
                </div>
            </header>
            <div id="chatMessages" class="chat-msgs"></div>
            <div class="chat-footer">
                <input type="text" id="msgText" placeholder="মেসেজ লিখুন...">
                <button class="btn-blue" style="width:60px; border-radius:20px; margin:0;" onclick="sendText()">➤</button>
            </div>
        </div>

    </div>

    <!-- ইনকামিং কল রিসিভ পপআপ -->
    <div id="incomingPop" class="ring-pop hidden">
        <div>
            <b id="callerId">017...</b><br>
            <span>কল দিচ্ছে...</span>
        </div>
        <div style="display:flex; gap:10px;">
            <button onclick="answerCall()" style="background:#2ecc71; border:none; padding:8px 15px; color:white; border-radius:5px;">রিসিভ</button>
            <button onclick="hangup()" style="background:#e74c3c; border:none; padding:8px 15px; color:white; border-radius:5px;">কাটুন</button>
        </div>
    </div>

    <!-- ভিডিও কল স্ক্রিন -->
    <div id="callScreen" class="call-ui hidden">
        <div class="video-container">
            <video id="remoteVideo" autoplay playsinline></video>
            <video id="localVideo" autoplay playsinline muted></video>
        </div>
        <div class="call-btns">
            <button class="btn-hangup" onclick="hangup()">✖</button>
        </div>
    </div>

    <script>
        const socket = io();
        let myId = null;
        let currentTarget = null;
        let localStream, peerConn, currentSignal;
        const rtcConf = { iceServers: [{ urls: 'stun:stun.l.google.com:19302' }] };

        // --- অটো লগইন লজিক ---
        window.onload = () => {
            const saved = localStorage.getItem('imo_login');
            if (saved) {
                const data = JSON.parse(saved);
                socket.emit('auth_user', data);
            }
        };

        function handleAuth() {
            const phone = document.getElementById('phoneInput').value.trim();
            const pin = document.getElementById('pinInput').value.trim();
            if (phone.length < 5 || pin.length < 4) return alert("সঠিক তথ্য দিন");
            const data = { phone, pin };
            socket.emit('auth_user', data);
        }

        socket.on('auth_success', data => {
            myId = data.phone;
            localStorage.setItem('imo_login', JSON.stringify({ phone: data.phone, pin: data.pin }));
            document.getElementById('authScreen').classList.add('hidden');
            document.getElementById('mainScreen').classList.remove('hidden');
            document.getElementById('myIdDisplay').innerText = myId;
            socket.emit('request_contacts');
        });

        function logout() {
            localStorage.removeItem('imo_login');
            location.reload();
        }

        // --- চ্যাট লজিক ---
        function startNewChat() {
            const target = document.getElementById('targetInput').value.trim();
            if (target) openChat(target);
        }

        function openChat(phone) {
            currentTarget = phone;
            document.getElementById('chatTitle').innerText = phone;
            document.getElementById('chatView').classList.remove('hidden');
            document.getElementById('chatMessages').innerHTML = "";
            socket.emit('load_history', { from: myId, to: phone });
        }

        function closeChat() {
            document.getElementById('chatView').classList.add('hidden');
            currentTarget = null;
        }

        function sendText() {
            const txt = document.getElementById('msgText').value.trim();
            if (!txt) return;
            const data = { from: myId, to: currentTarget, msg: txt };
            socket.emit('private_msg', data);
            addMsg(data, 'sent');
            document.getElementById('msgText').value = "";
        }

        socket.on('new_msg', data => {
            if (currentTarget === data.from) addMsg(data, 'recv');
            else alert("মেসেজ পাঠিয়েছে: " + data.from);
        });

        socket.on('history_data', msgs => {
            msgs.forEach(m => addMsg(m, m.from === myId ? 'sent' : 'recv'));
        });

        function addMsg(data, type) {
            const box = document.getElementById('chatMessages');
            const d = document.createElement('div');
            d.className = `m ${type}`;
            d.innerText = data.msg;
            box.appendChild(d);
            box.scrollTop = box.scrollHeight;
        }

        // --- ভিডিও/অডিও কল (WebRTC) ---
        async function makeCall(type) {
            document.getElementById('callScreen').classList.remove('hidden');
            localStream = await navigator.mediaDevices.getUserMedia({ video: type === 'video', audio: true });
            document.getElementById('localVideo').srcObject = localStream;

            peerConn = new RTCPeerConnection(rtcConf);
            localStream.getTracks().forEach(t => peerConn.addTrack(t, localStream));

            peerConn.onicecandidate = e => {
                if (e.candidate) socket.emit('call_signal', { to: currentTarget, candidate: e.candidate, from: myId });
            };
            peerConn.ontrack = e => {
                document.getElementById('remoteVideo').srcObject = e.streams[0];
            };

            const offer = await peerConn.createOffer();
            await peerConn.setLocalDescription(offer);
            socket.emit('call_signal', { to: currentTarget, offer: offer, from: myId, type: type });
        }

        socket.on('call_signal', async data => {
            if (data.offer) {
                currentSignal = data;
                document.getElementById('callerId').innerText = data.from;
                document.getElementById('incomingPop').classList.remove('hidden');
                document.getElementById('callRing').play();
            } else if (data.answer) {
                await peerConn.setRemoteDescription(new RTCSessionDescription(data.answer));
            } else if (data.candidate) {
                try { await peerConn.addIceCandidate(new RTCIceCandidate(data.candidate)); } catch(e) {}
            }
        });

        async function answerCall() {
            document.getElementById('callRing').pause();
            document.getElementById('incomingPop').classList.add('hidden');
            document.getElementById('callScreen').classList.remove('hidden');

            localStream = await navigator.mediaDevices.getUserMedia({ video: currentSignal.type === 'video', audio: true });
            document.getElementById('localVideo').srcObject = localStream;

            peerConn = new RTCPeerConnection(rtcConf);
            localStream.getTracks().forEach(t => peerConn.addTrack(t, localStream));

            peerConn.onicecandidate = e => {
                if (e.candidate) socket.emit('call_signal', { to: currentSignal.from, candidate: e.candidate, from: myId });
            };
            peerConn.ontrack = e => {
                document.getElementById('remoteVideo').srcObject = e.streams[0];
            };

            await peerConn.setRemoteDescription(new RTCSessionDescription(currentSignal.offer));
            const ans = await peerConn.createAnswer();
            await peerConn.setLocalDescription(ans);
            socket.emit('call_signal', { to: currentSignal.from, answer: ans, from: myId });
        }

        function hangup() {
            location.reload();
        }

        // কন্টাক্ট লিস্ট আপডেট
        socket.on('update_contacts', users => {
            const list = document.getElementById('contactList');
            list.innerHTML = "";
            users.forEach(u => {
                if (u.phone === myId) return;
                const div = document.createElement('div');
                div.className = 'contact';
                div.innerHTML = `<div class="avatar">${u.phone[0]}</div> <div><b>${u.phone}</b><br><span class="status-on">${u.status}</span></div>`;
                div.onclick = () => openChat(u.phone);
                list.appendChild(div);
            });
        });
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(html_template)

# --- ব্যাকএন্ড সকেট লজিক (Backend Logic) ---

@socketio.on('auth_user')
def auth_user(data):
    phone = str(data.get('phone'))
    pin = str(data.get('pin'))
    user = users_collection.find_one({"phone": phone})
    
    if user:
        if user['pin'] == pin:
            users_collection.update_one({"phone": phone}, {"$set": {"status": "online", "sid": request.sid}})
        else:
            emit('error', 'ভুল পিন!')
            return
    else:
        # নতুন ইউজার হলে একাউন্ট খুলে দেওয়া
        users_collection.insert_one({"phone": phone, "pin": pin, "status": "online", "sid": request.sid})
    
    emit('auth_success', {'phone': phone, 'pin': pin})
    send_contact_updates()

@socketio.on('load_history')
def load_history(data):
    history = list(messages_collection.find({
        "$or": [
            {"from": data['from'], "to": data['to']},
            {"from": data['to'], "to": data['from']}
        ]
    }, {"_id": 0}).sort("_id", 1))
    emit('history_data', history)

@socketio.on('private_msg')
def private_msg(data):
    messages_collection.insert_one({
        "from": data['from'],
        "to": data['to'],
        "msg": data['msg'],
        "time": datetime.datetime.now()
    })
    target = users_collection.find_one({"phone": data['to']})
    if target and target['status'] == 'online':
        emit('new_msg', data, room=target['sid'])

@socketio.on('call_signal')
def call_signal(data):
    target = users_collection.find_one({"phone": data['to']})
    if target and target['status'] == 'online':
        emit('call_signal', data, room=target['sid'])

@socketio.on('request_contacts')
def request_contacts():
    send_contact_updates()

def send_contact_updates():
    users = list(users_collection.find({}, {"_id": 0, "phone": 1, "status": 1}))
    socketio.emit('update_contacts', users)

@socketio.on('disconnect')
def on_disconnect():
    users_collection.update_one({"sid": request.sid}, {"$set": {"status": "offline"}})
    send_contact_updates()

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host='0.0.0.0', port=port)
