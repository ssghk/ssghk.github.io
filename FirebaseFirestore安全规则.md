rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {

match /users/{uid}/tokens/{token} {
  allow read: if true;
}

    // 類別集合
    match /categories/{doc} {
        allow read: if true;
        allow write: if request.auth != null && request.auth.uid == '109EjNOTmkh2CRuLghiIuwTDzl02';
      }

    // 公用廣告資料集合 ads
    match /ads/{doc} {
      allow read: if true;
      allow write: if request.auth != null && request.auth.uid == '109EjNOTmkh2CRuLghiIuwTDzl02';
    }

    match /users/{userId} {
      allow read: if true;

      allow update: if request.auth != null && (
        // 會員自己可編輯自己的付款方式
        (request.auth.uid == userId && request.resource.data.paymentMethods is list)
        // 管理員可編輯所有會員的付款方式
        || (get(/databases/$(database)/documents/users/$(request.auth.uid)).data.role == 'admin' && request.resource.data.paymentMethods is list)
      );

      // 只允許 Cloud Function 寫入統計欄位
      allow update: if request.auth != null &&
        request.auth.token.firebase.sign_in_provider == 'custom' &&
        request.resource.data.keys().hasOnly(['month', 'total', 'monthKey']);
      // 只允許管理員寫入會員資料（不能動統計欄位）
      allow update: if request.auth != null &&
        request.auth.uid == '109EjNOTmkh2CRuLghiIuwTDzl02' &&
        !('month' in request.resource.data) &&
        !('total' in request.resource.data) &&
        !('monthKey' in request.resource.data);
      allow write: if false;
    }
    // 網站資料規則
    match /site/main {
      allow read: if true;
      allow write: if request.auth != null && request.auth.uid == '109EjNOTmkh2CRuLghiIuwTDzl02';
    }

  }
}


