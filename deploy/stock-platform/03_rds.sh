#!/usr/bin/env bash
# Phase C. RDS MariaDB(거래) + RDS PostgreSQL(퀀트)
source "$(dirname "$0")/00_common.sh"
need PRI_A PRI_C SG_DB

step "[1/4] DB 서브넷 그룹"
aws rds describe-db-subnet-groups --db-subnet-group-name ${APP}-db-subnets >/dev/null 2>&1 || \
aws rds create-db-subnet-group --db-subnet-group-name ${APP}-db-subnets \
  --db-subnet-group-description "${APP} private subnets" --subnet-ids "$PRI_A" "$PRI_C" >/dev/null

get_secret() { aws ssm get-parameter --with-decryption --name "${SSM_PREFIX}/$1" --query Parameter.Value --output text; }
DB_PASS="$(get_secret db/mariadb/password)"
PG_PASS="$(get_secret db/postgres/password)"

create_db() { # id engine version dbname user pass
  if aws rds describe-db-instances --db-instance-identifier "$1" >/dev/null 2>&1; then echo "  (존재) $1"; return; fi
  aws rds create-db-instance --db-instance-identifier "$1" --engine "$2" --engine-version "$3" \
    --db-instance-class "$DB_INSTANCE_CLASS" --allocated-storage 20 --storage-type gp3 \
    --db-name "$4" --master-username "$5" --master-user-password "$6" \
    --vpc-security-group-ids "$SG_DB" --db-subnet-group-name ${APP}-db-subnets \
    --no-publicly-accessible --backup-retention-period 7 \
    --preferred-backup-window 18:00-19:00 --preferred-maintenance-window sun:19:30-sun:20:30 \
    --storage-encrypted --deletion-protection --tags Key=Project,Value="$APP" >/dev/null
  echo "  생성 요청: $1"
}

step "[2/4] MariaDB 11.4 (회원·모의 주문)"
create_db ${APP}-mariadb mariadb 11.4 "$MARIADB_NAME" "$MARIADB_USER" "$DB_PASS"
step "[3/4] PostgreSQL 16 (퀀트)"
create_db ${APP}-postgres postgres 16 "$PG_NAME" "$PG_USER" "$PG_PASS"

step "[4/4] available 대기 → 엔드포인트 → SSM 접속 문자열"
aws rds wait db-instance-available --db-instance-identifier ${APP}-mariadb
aws rds wait db-instance-available --db-instance-identifier ${APP}-postgres
save MARIADB_HOST "$(aws rds describe-db-instances --db-instance-identifier ${APP}-mariadb --query 'DBInstances[0].Endpoint.Address' --output text)"
save PG_HOST      "$(aws rds describe-db-instances --db-instance-identifier ${APP}-postgres --query 'DBInstances[0].Endpoint.Address' --output text)"
ssm_put db/mariadb/url  "mysql+pymysql://${MARIADB_USER}:${DB_PASS}@${MARIADB_HOST}:3306/${MARIADB_NAME}"
ssm_put db/postgres/url "postgresql+psycopg://${PG_USER}:${PG_PASS}@${PG_HOST}:5432/${PG_NAME}"
echo; echo "RDS 완료. 스키마는 앱 EC2 에서 적용: mysql -h $MARIADB_HOST ... / psql -h $PG_HOST ..."
