#!/bin/bash
export PGPASSWORD=%(db_password)s
pg_dump -U %(db_user)s %(db_name)s | gzip > %(backup_dir)s/%(project_name)s-`date '+%%Y%%m%%d'`.sql.gz
/usr/local/bin/aws s3 mv %(backup_dir)s/%(project_name)s-`date '+%%Y%%m%%d'`.sql.gz s3://%(backup_bucket)s