# APK analysis and reproducibility

Input supplied by the user: `nice-eljur.apk`.

- SHA-256: `6e5bc3a721987581b948b07d54d13e3cd86d7711a4a2997ef2fa974868c6a6a6`
- Main application namespace observed in DEX: `com.team.niceeljur`
- DEX files: `classes.dex`, `classes2.dex`, `classes3.dex`
- Decompiler used: JADX 1.5.3, Java 17
- Analysis date: 2026-10-17

The APK was unpacked and its DEX files decompiled. The full JADX pass processed 6,549 classes and reported 48 decompilation errors. The API interfaces and model declarations used for request contracts were readable. A fallback pass recovered the message attachment multipart field and success checks from the send-message coroutine. This is partial decompilation of an Android application, not a recovered buildable app source tree.

Reproduction (run outside the SDK checkout or keep output ignored):

```sh
sha256sum nice-eljur.apk
jadx --no-res -d decompiled nice-eljur.apk
# A nonzero status from the full pass may still leave usable output.
# Inspect the reported errors; do not silently treat incomplete output as verified.

jadx --no-res --decompilation-mode fallback \
  --single-class com.team.feature_send_message.presentation.SendMessageViewModel \
  --single-class-output send-fallback.java nice-eljur.apk
```

Inspect these classes under `decompiled/sources/com/team/`:

| Evidence | Details established |
| --- | --- |
| `common/ApiConstants.java` | Base origins, school vendor, devkey, User-Agent, JSON format |
| `common/di/NetworkModule.java` | Separate school/global Retrofit instances and unrelated telemetry backend |
| `feature_login/data/remote/LoginApi.java` | POST auth, body, header and query annotations |
| `feature_login/data/model/LoginRequest.java` | JSON `login`, `password` |
| `feature_login/data/model/TokenResult.java` | Token and string expiry |
| `feature_login/data/repository/LoginRepositoryImpl.java` | `response.state == 200` login success condition |
| `feature_diary/data/remote/DiaryApi.java` | Diary, rules, periods, rings and date range |
| `feature_marks/data/remote/MarksApi.java` | Marks and final-assessment routes |
| `feature_messages/data/remote/MessagesApi.java` | Message pagination and filtering |
| `feature_send_message/data/remote/MessageApi.java` | Receiver list, send body, dynamic upload |
| `feature_send_message/presentation/SendMessageViewModel.java` | Sender person ID, comma-separated recipients, uploaded file arrays |
| `feature_control_works/data/remote/ControlWorksApi.java` | Separate web AJAX route and default method |
| `feature_choose_school/data/remote/ChooseSchoolApi.java` | Global school search and options response |

The machine-readable endpoint inventory is derived from Retrofit annotations and contains protocol facts rather than decompiled implementations. Models were inspected separately to establish response nesting. No original application code, APK, extracted credentials, personal records, or embedded service keys are included in this repository. The SDK is an original implementation of the observed request contracts.

The APK also has a separate Supabase user-record integration. It is unrelated to the Eljur protocol and is not reproduced in the SDK.

## Verification boundary

The checked-in tests cover JSON login, token updates, all exposed route/query mappings, message payloads, multipart upload, isolated cookie jars, application and HTTP failures, invalid JSON, invalid date ranges, credential redaction, disabled redirects, no POST retries, and async use. All fixture data is synthetic. No live Eljur account was available; production compatibility is therefore unverified.
