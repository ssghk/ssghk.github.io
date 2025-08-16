rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /users/{userId} {
      allow read: if true;
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