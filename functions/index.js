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




// geturl 計數器，每次呼叫時 month +1, total +1, usageCount -1 (最小為0)，並回傳 url
// 比錢版 9s 月/最少 $0.62 USD
exports.incrementCount = functions
  .runWith({ minInstances: 1 })
  .https
  .onCall(async (data, context) => {
    const uid = data.uid;
    if (!uid) throw new functions.https.HttpsError('invalid-argument', 'Missing uid');

    try {
      const result = await admin.firestore().runTransaction(async (transaction) => {
        const userRef = admin.firestore().collection('users').doc(uid);
        const doc = await transaction.get(userRef);
        if (!doc.exists) throw new functions.https.HttpsError('not-found', 'User not found');

        const userData = doc.data();
        const now = new Date();
        const monthKey = now.getFullYear() + '-' + (now.getMonth() + 1);
        let month = userData.month || 0;
        let total = userData.total || 0;

        // 如果月份切换，重置月计数
        if (userData.monthKey !== monthKey) month = 0;

        month++;
        total++;

        let usageCount = (userData.usageCount || 0) - 1;
        //if (usageCount < 0) usageCount = 0;
        let lastGetDate = now.toISOString();

        // 准备更新数据
        transaction.update(userRef, {
          month,
          total,
          monthKey,
          usageCount,
          lastGetDate
        });

        // 直接返回URL，避免第二次读操作
        return { url: userData.url };
      });

      return result; // 返回 { url: ... }

    } catch (error) {
      // 错误处理
      if (error instanceof functions.https.HttpsError) throw error;
      console.error('Transaction failure:', error);
      throw new functions.https.HttpsError('internal', '操作失败');
    }
  });
/*
// 免費優化版 14s
exports.incrementCount = functions.https.onCall(async (data, context) => {
  const uid = data.uid;
  if (!uid) throw new functions.https.HttpsError('invalid-argument', 'Missing uid');
  
  const userRef = admin.firestore().collection('users').doc(uid);
  const doc = await userRef.get();
  
  if (!doc.exists) throw new functions.https.HttpsError('not-found', 'User not found');
  
  const now = new Date();
  const monthKey = now.getFullYear() + '-' + (now.getMonth() + 1);
  const userData = doc.data();
  
  let month = userData.month || 0;
  let total = userData.total || 0;
  
  // 检查是否需要重置月度计数
  if (userData.monthKey !== monthKey) month = 0;
  
  month++;
  total++;
  
  // 更新 usageCount 和 lastGetDate
  let usageCount = (userData.usageCount || 0) - 1;
  if (usageCount < 0) usageCount = 0;
  let lastGetDate = now.toISOString();
  
  // 执行更新操作
  await userRef.update({ 
    month, 
    total, 
    monthKey, 
    usageCount, 
    lastGetDate 
  });
  
  // 直接返回第一次获取的 URL，避免第二次读取
  return { url: userData.url };
});
*/




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