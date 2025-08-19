/*
cd C:\Users\mokaki\Desktop\金\ssghk.github.io
firebase deploy --only functions
*/

const functions = require('firebase-functions');
const admin = require('firebase-admin');
admin.initializeApp();



const { v4: uuidv4 } = require('uuid');
// 產生一次性 token，30天有效
exports.createTokenForUser = functions.https.onCall(async (data, context) => {
  const uid = data.uid;
  if (!uid) throw new functions.https.HttpsError('invalid-argument', 'Missing uid');
  const now = new Date();
  const expireAt = new Date(now.getTime() + 30 * 24 * 60 * 60 * 1000); // 30天
  const token = uuidv4();
  await admin.firestore().collection('users').doc(uid).collection('tokens').doc(token).set({
    createdAt: now.toISOString(),
    expireAt: expireAt.toISOString(),
    uid
  });
  return { token, expireAt: expireAt.toISOString() };
});



// 新用戶註冊時自動建立 Firestore users 文件
exports.createUserDocument = functions.auth.user().onCreate(async (user) => {
  const uid = user.uid;
  const name = user.displayName || '';
  const url = `https://ssghk.github.io/index.html?user=${uid}`;
  const geturl = `https://ssghk.github.io/index.html?get=${uid}`;
  const localUrl = `http://127.0.0.1:5500/index.html?user=${uid}`;
  const localGeturl = `http://127.0.0.1:5500/index.html?get=${uid}`;
  await admin.firestore().collection('users').doc(uid).set({
    name,
    vip: false,
    url,
    geturl,
    localUrl,
    localGeturl,
    month: 0,
    total: 0,
    usageCount: 0,
    lastGetDate: ''
  });
});

exports.incrementCount = functions.https.onCall(async (data, context) => {
  const uid = data.uid;
  if (!uid) throw new functions.https.HttpsError('invalid-argument', 'Missing uid');
  const userRef = admin.firestore().collection('users').doc(uid);
  const doc = await userRef.get();
  if (!doc.exists) throw new functions.https.HttpsError('not-found', 'User not found');
  const now = new Date();
  const monthKey = now.getFullYear() + '-' + (now.getMonth() + 1);
  let month = doc.data().month || 0;
  let total = doc.data().total || 0;
  if (doc.data().monthKey !== monthKey) month = 0;
  month++; total++;
  // 新增 usageCount 與 lastGetDate（usageCount 每次減 1，最小為 0）
  let usageCount = (doc.data().usageCount || 0) - 1;
  if (usageCount < 0) usageCount = 0;
  let lastGetDate = now.toISOString();
  await userRef.update({ month, total, monthKey, usageCount, lastGetDate });
  // 重新取得最新資料
  const updatedDoc = await userRef.get();
  return { url: updatedDoc.data().url };
});
// 管理員可修改 usageCount, lastGetDate 欄位
exports.adminUpdateUserExtra = functions.https.onCall(async (data, context) => {
  const adminUid = '109EjNOTmkh2CRuLghiIuwTDzl02';
  if (context.auth?.uid !== adminUid) {
    throw new functions.https.HttpsError('permission-denied', '只有管理員可操作');
  }
  const { uid, usageCount, lastGetDate } = data;
  const update = {};
  if (typeof usageCount === 'number') update.usageCount = usageCount;
  if (typeof lastGetDate === 'string') update.lastGetDate = lastGetDate;
  await admin.firestore().collection('users').doc(uid).update(update);
  return { success: true };
});

// 儲存會員資料
exports.updateUserProfile = functions.https.onCall(async (data, context) => {
  if (!context.auth) {
    throw new functions.https.HttpsError('unauthenticated', '請先登入');
  }
  const uid = context.auth.uid;
  const { name, phone, address, logo, ads } = data;
  await admin.firestore().collection('users').doc(uid).update({
    name, phone, address, logo, ads
  });
  return { success: true };
});

// 管理員更新會員資料
exports.adminUpdateUser = functions.https.onCall(async (data, context) => {
  // 僅允許 admin 帳號
  const adminUid = '109EjNOTmkh2CRuLghiIuwTDzl02'; // 請填入第一個註冊者UID
  if (context.auth?.uid !== adminUid) {
    throw new functions.https.HttpsError('permission-denied', '只有管理員可操作');
  }
  const { uid, update } = data;
  await admin.firestore().collection('users').doc(uid).update(update);
  return { success: true };
});

// 公用廣告資料管理
exports.updateAdList = functions.https.onCall(async (data, context) => {
  const adminUid = '109EjNOTmkh2CRuLghiIuwTDzl02'; // 請填入你的管理員UID
  if (context.auth?.uid !== adminUid) {
    throw new functions.https.HttpsError('permission-denied', '只有管理員可操作');
  }
  // data.ads: 陣列，每個物件有 img, title, desc1, desc2
  if (!Array.isArray(data.ads)) {
    throw new functions.https.HttpsError('invalid-argument', 'ads 必須為陣列');
  }
  await admin.firestore().collection('ads').doc('main').set({ ads: data.ads });
  return { success: true };
});