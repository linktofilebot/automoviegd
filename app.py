# ১. সবার আগে eventlet monkey patch (অবশ্যই সবার উপরে থাকবে)
import eventlet
eventlet.monkey_patch()

import os
from flask import Flask, render_template_string, request
from flask_socketio import SocketIO, emit
from pymongo import MongoClient

# --- অ্যাপ সেটআপ ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'video-call-secure-key-2026'
# async_mode হিসেবে eventlet ব্যবহার করা হয়েছে
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# --- মোঙ্গোডিবি (MongoDB) কানেকশন ---
# এখানে আপনার আসল MongoDB URI দিবেন
MONGO_URI = "mongodb+srv://Demo270:Demo270@cluster0.ls1igsg.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0" 

users_collection = None

try:
    # কানেকশন করার চেষ্টা
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    db = client['video_call_system']
    users_collection = db['users']
    # কানেকশন টেস্ট
    client.admin.command('ping')
    print("✅ MongoDB Connected Successfully!")
except Exception as e:
    print(f"❌ Database Connection Error: {e}")

# --- ফ্রন্টএন্ড কোড (HTML/CSS/JS) ---
html_content = """
<!DOCTYPE html>
<html lang="bn">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>প্রাইভেট ভিডিও ও অডিও কল</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <style>
        :root { --primary: #6c5ce7; --success: #2ed573; --danger: #ff4757; }
        body { font-family: 'Segoe UI', sans-serif; background: #f1f2f6; margin: 0; display: flex; align-items: center; justify-content: center; height: 100vh; overflow: hidden; }
        
        .hidden { display: none !important; }
        
        .card { background: white; width: 95%; max-width: 400px; padding: 25px; border-radius: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.1); text-align: center; }
        input { width: 100%; padding: 12px; margin: 10px 0; border: 2px solid #edeff2; border-radius: 12px; font-size: 16px; box-sizing: border-box; outline: none; transition: 0.3s; }
        input:focus { border-color: var(--primary); }
        button { width: 100%; padding: 12px; border: none; border-radius: 12px; font-weight: bold; cursor: pointer; margin-top: 10px; color: white; font-size: 16px; }
        
        .btn-login { background: var(--primary); }
        .btn-video { background: var(--success); }
        .btn-audio { background: #1e90ff; }
        .btn-hangup { background: var(--danger); }
        
        .video-box { margin-top: 20px; display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
        video { width: 100%; background: #000; border-radius: 12px; transform: scaleX(-1); }
        
        .overlay { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.9); z-index: 9999; display: flex; flex-direction: column; align-items: center; justify-content: center; color: white; }
        .status-dot { height: 10px; width: 10px; background-color: var(--success); border-radius: 50%; display: inline-block; margin-right: 5px; }
        .link-text { color: var(--primary); cursor: pointer; text-decoration: underline; display: block; margin-top: 15px; font-size: 14px; }
    </style>
</head>
<body>

    <audio id="audioRing" src="https://assets.mixkit.co/active_storage/sfx/1359/1359-preview.mp3" loop></audio>
    <audio id="videoRing" src="https://www.soundjay.com/phone/phone-calling-1.mp3" loop></audio>

    <!-- ১. রেজিস্ট্রেশন বক্স -->
    <div class="card" id="registerBox">
        <h2 style="color: var(--primary);">একাউন্ট তৈরি করুন</h2>
        <input type="number" id="regPhone" placeholder="মোবাইল নাম্বার">
        <input type="password" id="regPin" placeholder="৫ ডিজিটের সিক্রেট পিন" maxlength="5">
        <button class="btn-login" onclick="registerAccount()">একাউন্ট খুলুন</button>
        <span class="link-text" onclick="showLogin()">ইতিমধ্যে একাউন্ট আছে? লগইন করুন</span>
    </div>

    <!-- ২. লগইন বক্স -->
    <div class="card hidden" id="loginBox">
        <h2 style="color: var(--primary);">লগইন করুন</h2>
        <input type="number" id="loginPhone" placeholder="মোবাইল নাম্বার">
        <input type="password" id="loginPin" placeholder="পিন কোড দিন">
        <button class="btn-login" onclick="login()">লগইন করুন</button>
        <span class="link-text" onclick="showRegister()">নতুন একাউন্ট তৈরি করুন</span>
    </div>

    <!-- ৩. মেইন ড্যাশবোর্ড -->
    <div class="card hidden" id="dashboard">
        <div style="margin-bottom: 15px;">
            <span class="status-dot"></span> আইডি: <b id="myIdDisplay"></b>
        </div>
        <input type="number" id="searchId" placeholder="বন্ধুর নাম্বার লিখুন">
        <div style="display: flex; gap: 10px;">
            <button class="btn-video" onclick="initiateCall('video')">ভিডিও কল</button>
            <button class="btn-audio" onclick="initiateCall('audio')">অডিও কল</button>
        </div>

        <div id="callInterface" class="hidden">
            <p id="callStatus" style="font-weight: bold; margin-top: 15px; color: red;">কল চলছে...</p>
            <div class="video-box">
                <video id="localVideo" autoplay playsinline muted></video>
                <video id="remoteVideo" autoplay playsinline></video>
            </div>
            <button class="btn-hangup" onclick="endCall()">কল কাটুন</button>
        </div>
    </div>

    <!-- ৪. ইনকামিং কল পপআপ -->
    <div id="incomingPopup" class="overlay hidden">
        <h1 id="callerIdHead">017XXXXXXXX</h1>
        <p id="callTypeHead">কল দিচ্ছে...</p>
        <div style="display: flex; gap: 20px; margin-top: 20px;">
            <button class="btn-video" style="width: 150px;" onclick="acceptCall()">রিসিভ</button>
            <button class="btn-hangup" style="width: 150px;" onclick="endCall()">কাটুন</button>
        </div>
    </div>

    <script>
        const socket = io();
        let myId, localStream, peerConnection, currentOffer;
        const rtcConfig = { iceServers: [{ urls: 'stun:stun.l.google.com:19302' }] };

        function showLogin() {
            document.getElementById('registerBox').classList.add('hidden');
            document.getElementById('loginBox').classList.remove('hidden');
        }
        function showRegister() {
            document.getElementById('loginBox').classList.add('hidden');
            document.getElementById('registerBox').classList.remove('hidden');
        }

        function registerAccount() {
            const phone = document.getElementById('regPhone').value.trim();
            const pin = document.getElementById('regPin').value.trim();
            if (phone.length < 5 || pin.length !== 5) return alert("সঠিক নাম্বার ও ৫ ডিজিটের পিন দিন");
            socket.emit('register_new_user', { phone, pin });
        }

        socket.on('register_response', data => {
            alert(data.message);
            if (data.status === 'success') showLogin();
        });

        function login() {
            const phone = document.getElementById('loginPhone').value.trim();
            const pin = document.getElementById('loginPin').value.trim();
            if (!phone || !pin) return alert("তথ্য দিন");
            socket.emit('login_user', { phone, pin });
        }

        socket.on('login_response', data => {
            if (data.status === 'success') {
                myId = data.phone;
                document.getElementById('loginBox').classList.add('hidden');
                document.getElementById('dashboard').classList.remove('hidden');
                document.getElementById('myIdDisplay').innerText = myId;
            } else {
                alert(data.message);
            }
        });

        async function initiateCall(type) {
            const target = document.getElementById('searchId').value.trim();
            if (!target || target === myId) return alert("সঠিক নাম্বার দিন");

            try {
                localStream = await navigator.mediaDevices.getUserMedia({ video: type === 'video', audio: true });
                document.getElementById('localVideo').srcObject = localStream;
                document.getElementById('callInterface').classList.remove('hidden');

                peerConnection = new RTCPeerConnection(rtcConfig);
                localStream.getTracks().forEach(track => peerConnection.addTrack(track, localStream));

                peerConnection.onicecandidate = e => {
                    if (e.candidate) socket.emit('signal_data', { to: target, candidate: e.candidate, from: myId });
                };
                peerConnection.ontrack = e => {
                    document.getElementById('remoteVideo').srcObject = e.streams[0];
                };

                const offer = await peerConnection.createOffer();
                await peerConnection.setLocalDescription(offer);
                socket.emit('signal_data', { to: target, offer: offer, from: myId, type: type });
            } catch (err) {
                alert("ক্যামেরা বা মাইক্রোফোন এক্সেস দিন!");
            }
        }

        socket.on('signal_data', async (data) => {
            if (data.offer) {
                currentOffer = data;
                document.getElementById('callerIdHead').innerText = data.from;
                document.getElementById('callTypeHead').innerText = data.type === 'video' ? "ভিডিও কল দিচ্ছে..." : "অডিও কল দিচ্ছে...";
                document.getElementById('incomingPopup').classList.remove('hidden');
                document.getElementById(data.type === 'video' ? 'videoRing' : 'audioRing').play();
            } else if (data.answer) {
                await peerConnection.setRemoteDescription(new RTCSessionDescription(data.answer));
            } else if (data.candidate) {
                try { await peerConnection.addIceCandidate(new RTCIceCandidate(data.candidate)); } catch(e) {}
            }
        });

        async function acceptCall() {
            document.getElementById('videoRing').pause();
            document.getElementById('audioRing').pause();
            document.getElementById('incomingPopup').classList.add('hidden');
            document.getElementById('callInterface').classList.remove('hidden');

            localStream = await navigator.mediaDevices.getUserMedia({ video: currentOffer.type === 'video', audio: true });
            document.getElementById('localVideo').srcObject = localStream;

            peerConnection = new RTCPeerConnection(rtcConfig);
            localStream.getTracks().forEach(track => peerConnection.addTrack(track, localStream));

            peerConnection.onicecandidate = e => {
                if (e.candidate) socket.emit('signal_data', { to: currentOffer.from, candidate: e.candidate, from: myId });
            };
            peerConnection.ontrack = e => {
                document.getElementById('remoteVideo').srcObject = e.streams[0];
            };

            await peerConnection.setRemoteDescription(new RTCSessionDescription(currentOffer.offer));
            const answer = await peerConnection.createAnswer();
            await peerConnection.setLocalDescription(answer);
            socket.emit('signal_data', { to: currentOffer.from, answer: answer, from: myId });
        }

        function endCall() { location.reload(); }
        socket.on('error_msg', msg => alert(msg));
    </script>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(html_content)

# --- ব্যাকএন্ড সকেট লজিক ---

@socketio.on('register_new_user')
def register_new_user(data):
    if users_collection is None:
        emit('register_response', {'status': 'error', 'message': 'ডেটাবেস সংযুক্ত নয়!'})
        return
    phone = str(data.get('phone'))
    pin = str(data.get('pin'))
    try:
        existing_user = users_collection.find_one({"phone": phone})
        if existing_user:
            emit('register_response', {'status': 'error', 'message': 'এই নাম্বার ইতিমধ্যে আছে!'})
        else:
            users_collection.insert_one({"phone": phone, "pin": pin, "socket_id": request.sid, "status": "offline"})
            emit('register_response', {'status': 'success', 'message': 'একাউন্ট তৈরি সফল! লগইন করুন।'})
    except Exception as e:
        emit('register_response', {'status': 'error', 'message': 'সার্ভার সমস্যা!'})

@socketio.on('login_user')
def login_user(data):
    if users_collection is None:
        return
    phone = str(data.get('phone'))
    pin = str(data.get('pin'))
    try:
        user = users_collection.find_one({"phone": phone, "pin": pin})
        if user:
            users_collection.update_one({"phone": phone}, {"$set": {"socket_id": request.sid, "status": "online"}})
            emit('login_response', {'status': 'success', 'phone': phone})
        else:
            emit('login_response', {'status': 'error', 'message': 'ভুল নাম্বার বা পিন!'})
    except Exception as e:
        print(f"Login Error: {e}")

@socketio.on('signal_data')
def signal(data):
    if users_collection is None: return
    target_phone = str(data.get('to'))
    user = users_collection.find_one({"phone": target_phone})
    if user and user['status'] == 'online':
        emit('signal_data', data, room=user['socket_id'])
    else:
        emit('error_msg', "ইউজার অফলাইন!", room=request.sid)

# ডিসকানেক্ট ফাংশন ফিক্স করা হয়েছে (আর্গুমেন্ট গ্রহণ করার জন্য)
@socketio.on('disconnect')
def disconnect(*args):
    # 'if users_collection:' এর পরিবর্তে 'is not None' চেক করা হয়েছে
    if users_collection is not None:
        users_collection.update_one({"socket_id": request.sid}, {"$set": {"status": "offline"}})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host='0.0.0.0', port=port)
