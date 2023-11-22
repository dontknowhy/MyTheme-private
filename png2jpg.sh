#!/bin/bash
##convert
for image in *.png;
do
	convert  "$image"  "${image%.png}.jpg"
	echo “image $image converted to ${image%.png}.jpg ”
done
exit 0
