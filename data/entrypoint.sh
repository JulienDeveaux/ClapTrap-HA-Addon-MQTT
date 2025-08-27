#!/bin/sh

# Exit if /config is not mounted
if [ ! -d /config ]; then
	echo "Error: /config not mounted"
    exit 0
fi

# Default location
CONFIGSOURCE="/data/options.json"


# transform each options.json key to env var
for key in $(jq -r 'keys[]' $CONFIGSOURCE); do
    value=$(jq -r ".$key" $CONFIGSOURCE)
    key=$(echo "$key" | tr '[:lower:]' '[:upper:]' | tr '-' '_')

    # add to env
    export "$key=$value"
done

exec "$@"