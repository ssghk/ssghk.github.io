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

      // 允許管理員更新任何字段（包括付款方式）
      allow update: if request.auth != null && (
        // 管理員可以更新所有字段
        request.auth.uid == '109EjNOTmkh2CRuLghiIuwTDzl02'
        ||
        // 會員自己只能更新付款方式
        (request.auth.uid == userId && request.resource.data.paymentMethods is list)
      );


      // 會員自己只能新增/更新 email 欄位
      allow update: if request.auth != null &&
        request.auth.uid == userId &&
        request.resource.data.keys().hasOnly(['email']);



      // 只允許 Cloud Function 寫入統計欄位
      allow update: if request.auth != null &&
        request.auth.token.firebase.sign_in_provider == 'custom' &&
        request.resource.data.keys().hasOnly(['month', 'total', 'monthKey']);
      
      allow write: if false;
    }
    
    // 網站資料規則
    match /site/main {
      allow read: if true;
      allow write: if request.auth != null && request.auth.uid == '109EjNOTmkh2CRuLghiIuwTDzl02';
    }
  }
}