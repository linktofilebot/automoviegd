import os
from flask import Flask, render_template_string, request
from flask_socketio import SocketIO, emit
from pymongo import MongoClient

# --- অ্যাপ সেটআপ ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'super-secret-key-123'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# --- মোঙ্গোডিবি (MongoDB) কানেকশন ---
# এখানে আপনার আসল MongoDB URI টি দিবেন
MONGO_URI = "mongodb+srv://user:pass@cluster.mongodb.net/myDatabase?retryWrites=true&w=majority" 

try:
    client = MongoClient(MONGO_URI)
    db = client['video_call_system']
    users_collection = db['users']
except Exception as e:
    print(f"Database Connection Error: {e}")

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
        :root { --primary: #6c5ce7; --success: #2ed573; --danger: #ff4757; --dark: #2f3542; }
        body { font-family: 'Segoe UI', sans-serif; background: #f1f2f6; margin: 0; display: flex; align-items: center; justify-content: center; height: 100vh; overflow: hidden; }
        .card { background: white; width: 95%; max-width: 400px; padding: 25px; border-radius: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.1); text-align: center; }
        input { width: 100%; padding: 12px; margin: 10px 0; border: 2px solid #edeff2; border-radius: 12px; font-size: 16px; box-sizing: border-box; transition: 0.3s; }
        input:focus { border-color: var(--primary); outline: none; }
        button { width: 100%; padding: 12px; border: none; border-radius: 12px; font-weight: bold; cursor: pointer; transition: 0.3s; margin-top: 10px; color: white; font-size: 16px; }
        .btn-login { background: var(--primary); }
        .btn-video { background: var(--success); }
        .btn-audio { background: #1e90ff; }
        .btn-hangup { background: var(--danger); }
        .hidden { display: none; }
        .video-box { position: relative; width: 100%; margin-top: 20px; display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
        video { width: 100%; background: #000; border-radius: 12px; transform: scaleX(-1); }
        .overlay { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.9); z-index: 1000; display: flex; flex-direction: column; align-items: center; justify-content: center; color: white; }
        .status-dot { height: 10px; width: 10px; background-color: var(--success); border-radius: 50%; display: inline-block; margin-right: 5px; }
        .link-text { color: var(--primary); cursor: pointer; text-decoration: underline; display: block; margin-top: 15px; font-size: 14px; }
    </style>
</head>
<body>

    <!-- রিংটোন অডিও -->
    <audio id="audioRing" src="https://assets.mixkit.co/active_storage/sfx/1359/1359-preview.mp3" loop></audio>
    <audio id="videoRing" src="https://www.soundjay.com/phone/phone-calling-1.mp3" loop></audio>

    <!-- রেজিস্ট্রেশন স্ক্রিন (নতুন যোগ করা) -->
    <div class="card" id="registerBox">
        <h2 style="color: var(--primary);">একাউন্ট তৈরি করুন</h2>
        <input type="number" id="regPhone" placeholder="মোবাইল নাম্বার">
        <input type="password" id="regPin" placeholder="৫ ডিজিটের কোড দিন" maxlength="5">
        <button class="btn-login" onclick="registerAccount()">একাউন্ট খুলুন</button>
        <span class="link-text" onclick="showLogin()">ইতিমধ্যে একাউন্ট আছে? লগইন করুন</span>
    </div>

    <!-- লগইন স্ক্রিন (আপডেটেড) -->
    <div class="card hidden" id="loginBox">
        <h2 style="color: var(--primary);">লগইন করুন</h2>
        <input type="number" id="loginPhone" placeholder="মোবাইল নাম্বার">
        <input type="password" id="loginPin" placeholder="৫ ডিজিটের কোড দিন">
        <button class="btn-login" onclick="login()">লগইন করুন</button>
        <span class="link-text" onclick="showRegister()">নতুন একাউন্ট তৈরি করুন</span>
    </div>

    <!-- মেইন ড্যাশবোর্ড -->
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
            <p id="callStatus" style="font-weight: bold; margin-top: 15px;">সংযুক্ত হচ্ছে...</p>
            <div class="video-box">
                <video id="localVideo" autoplay playsinline muted></video>
                <video id="remoteVideo" autoplay playsinline></video>
            </div>
            <button class="btn-hangup" onclick="endCall()">কল কাটুন</button>
        </div>
    </div>

    <!-- ইনকামিং কল পপআপ -->
    <div id="incomingPopup" class="overlay hidden">
        <h1 id="callerIdHead">017XXXXXXXX</h1>
        <p id="callTypeHead">ভিডিও কল দিচ্ছে...</p>
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

        // ১. একাউন্ট তৈরি (Backend call)
        function registerAccount() {
            const phone = document.getElementById('regPhone').value;
            const pin = document.getElementById('regPin').value;
            if (phone.length < 10 || pin.length !== 5) return alert("সঠিক নাম্বার ও ৫ ডিজিটের কোড দিন");
            socket.emit('register_new_user', { phone, pin });
        }

        socket.on('register_response', data => {
            alert(data.message);
            if (data.status === 'success') showLogin();
        });

        // ২. লগইন (Backend call)
        function login() {
            const phone = document.getElementById('loginPhone').value;
            const pin = document.getElementById('loginPin').value;
            if (!phone || !pin) return alert("নাম্বার এবং পিন উভয়ই দিন");
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

        // ৩. কল শুরু করা (WebRTC)
        async function initiateCall(type) {
            const target = document.getElementById('searchId').value;
            if (!target || target === myId) return alert("সঠিক নাম্বার দিন");

            document.getElementById('callInterface').classList.remove('hidden');
            document.getElementById('callStatus').innerText = type.toUpperCase() + " কল যাচ্ছে...";

            localStream = await navigator.mediaDevices.getUserMedia({ video: type === 'video', audio: true });
            document.getElementById('localVideo').srcObject = localStream;

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
        }

        // ৪. সিগন্যালিং রিসিভ
        socket.on('signal_data', async (data) => {
            if (data.offer) {
                currentOffer = data;
                document.getElementById('callerIdHead').innerText = data.from;
                document.getElementById('callTypeHead').innerText = data.type === 'video' ? "ভিডিও কল দিচ্ছে..." : "অডিও কল দিচ্ছে...";
                document.getElementById(data.type === 'video' ? 'videoRing' : 'audioRing').play();
                document.getElementById('incomingPopup').classList.remove('hidden');
            } else if (data.answer) {
                await peerConnection.setRemoteDescription(new RTCSessionDescription(data.answer));
                document.getElementById('callStatus').innerText = "কথা বলুন";
            } else if (data.candidate) {
                try { await peerConnection.addIceCandidate(new RTCIceCandidate(data.candidate)); } catch(e) {}
            }
        });

        // ৫. কল রিসিভ
        async function acceptCall() {
            document.getElementById('videoRing').pause();
            document.getElementById('audioRing').pause();
            document.getElementById('incomingPopup').classList.add('hidden');
            document.getElementById('callInterface').classList.remove('hidden');

            localStream = await navigator.mediaDevices.getUserMedia({ 
                video: currentOffer.type === 'video', 
                audio: true 
            });
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

        function endCall() {
            location.reload();
        }

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
    phone = data.get('phone')
    pin = data.get('pin')
    
    # চেক করা হচ্ছে একাউন্ট আগে থেকে আছে কি না
    existing_user = users_collection.find_one({"phone": phone})
    if existing_user:
        emit('register_response', {'status': 'error', 'message': 'এই নাম্বার দিয়ে ইতিমধ্যে একাউন্ট খোলা আছে!'})
    else:
        users_collection.insert_one({
            "phone": phone,
            "pin": pin,
            "socket_id": request.sid,
            "status": "offline"
        })
        emit('register_response', {'status': 'success', 'message': 'একাউন্ট তৈরি সফল হয়েছে! এখন লগইন করুন।'})

@socketio.on('login_user')
def login_user(data):
    phone = data.get('phone')
    pin = data.get('pin')
    
    # ফোন ও পিন ম্যাচ করানো
    user = users_collection.find_one({"phone": phone, "pin": pin})
    if user:
        users_collection.update_one(
            {"phone": phone},
            {"$set": {"socket_id": request.sid, "status": "online"}}
        )
        emit('login_response', {'status': 'success', 'phone': phone})
    else:
        emit('login_response', {'status': 'error', 'message': 'ভুল নাম্বার অথবা পিন!'})

@socketio.on('signal_data')
def signal(data):
    target_phone = data.get('to')
    user = users_collection.find_one({"phone": target_phone})
    if user and user['status'] == 'online':
        emit('signal_data', data, room=user['socket_id'])
    else:
        emit('error_msg', "ইউজার অফলাইন বা ভুল নাম্বার!", room=request.sid)

@socketio.on('disconnect')
def disconnect():
    users_collection.update_one({"socket_id": request.sid}, {"$set": {"status": "offline"}})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=True)
