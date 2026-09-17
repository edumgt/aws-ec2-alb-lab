# AWS CLI로 S3 목록 조회하기

## 모든 S3 버킷 목록 조회

```bash
aws s3 ls
```

## 특정 버킷 내부 목록 조회

```bash
aws s3 ls s3://버킷이름/
```

## 하위 경로까지 재귀적으로 조회

```bash
aws s3 ls s3://버킷이름/ --recursive
```

## 프로필과 리전 지정

```bash
aws s3 ls s3://버킷이름/ --profile my-profile --region ap-northeast-2
```


54.116.203.151