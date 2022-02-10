#!/usr/bin/env bash

LS_COMMAND="ls -v test_*.py"
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
   pytest -xvrPA "$i"
done
echo -e "\e[1mTests completed on the following files:"
echo -e "$($LS_COMMAND)" 

