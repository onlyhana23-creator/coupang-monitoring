# Vercel 새 프로젝트 배포 가이드

이 저장소는 쿠팡 모니터링 대시보드 전용으로 분리되었습니다.
저장소 루트 = 프로젝트 루트이므로 Vercel Root Directory 설정 불필요합니다.

## 1. GitHub에 새 저장소 생성

1. GitHub → New repository
2. 이름 예: `coupang-monitoring` 또는 `hana-monitoring`
3. Public, **README 추가하지 않음** (로컬에 이미 커밋 있음)

## 2. 원격 추가 후 푸시

```bash
cd /Users/user/Cursor/coupang-monitoring-vercel

# GitHub 저장소 URL을 본인 것으로 교체
git remote add origin https://github.com/YOUR_USERNAME/coupang-monitoring.git
git branch -M main
git push -u origin main
```

## 3. Vercel에서 Import

1. [vercel.com](https://vercel.com) → Add New → Project
2. **Import Git Repository**에서 방금 푸시한 저장소 선택
3. **Root Directory**: 비워 둠 (저장소 루트 = 프로젝트 루트)
4. Deploy

## 4. 환경 변수 (필요 시)

Vercel 프로젝트 Settings → Environment Variables에서:

- `DATABASE_URL`: Neon PostgreSQL 등 (선택)
- `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`, `CONFLUENCE_SPACE_KEY`: config.yaml 값과 동일하게 설정
