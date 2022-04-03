#!/usr/bin/env bash

LS_COMMAND="ls -v test_*.py"
TEST_COMMAND="pytest -xvrPA -n auto"
# uncomment this to run linearly (not using multiple cores)
# TEST_COMMAND="pytest -xvrPA"
BOLD_TEXT="\e[1m"
GREEN_TEXT="\e[32m"
PLAIN_TEXT="\e[0m"

echo -e "About to run the following test files:"
echo -e "$($LS_COMMAND)" 
read -p "Proceed (y/N)? " -n 1 -r
echo

if [[ ! $REPLY =~ ^[Yy]$ ]]
then
    [[ "$0" = "$BASH_SOURCE" ]] && exit 1 || return 1 # handle exits from shell or function but don't exit interactive shell
fi

for i in $($LS_COMMAND)
do
   echo -e "${BOLD_TEXT}Now running ${GREEN_TEXT}$i ${PLAIN_TEXT}"
   ${TEST_COMMAND} "$i" || { printf '\n\n%s\n\n' "Test failed!  Assuming the code is fine, check you're in a properly set-up Cairo virtual environment: see README file or https://www.cairo-lang.org/docs/quickstart.html#installation" >&2; exit 1; }

done
echo -e "${BOLD_TEXT}Tests completed on the following files:"
echo -e "$($LS_COMMAND)" 

