#!/bin/bash
roles="customer hotel availability reservation payment notification"
fail=0

for r in $roles; do
  db="${r}_db"
  out="$(psql -U "$r" -d "$db" -tAc 'SELECT 1' 2>&1)"
  if [ "$out" != "1" ]; then
    echo "FALLO: $r no puede leer su propia BD $db ($out)"
    fail=1
  fi
done

for r in $roles; do
  for other in $roles; do
    [ "$r" = "$other" ] && continue
    db="${other}_db"
    if psql -U "$r" -d "$db" -tAc 'SELECT 1' >/dev/null 2>&1; then
      echo "FALLO: $r puede leer la BD ajena $db"
      fail=1
    fi
  done
done

if [ "$fail" -eq 0 ]; then
  echo "OK: cada rol accede solo a su BD; aislamiento de privilegios verificado."
fi
exit "$fail"
