# USAGE
# python pi_surveillance.py --conf conf.json

# import the necessary packages
from pyimagesearch.tempimage import TempImage
from picamera.array import PiRGBArray
from picamera import PiCamera
import argparse
import warnings
import datetime
import imutils
import json
import time
import cv2
import requests

#parse the arguments
ap = argparse.ArgumentParser()
ap.add_argument("-c", "--conf", required=True,
	help="path to the JSON configuration file")
args = vars(ap.parse_args())

# load the config
warnings.filterwarnings("ignore")
conf = json.load(open(args["conf"]))
client = None

# get api info
user = conf['api_user']
password = conf['api_password']
path = conf['api_path']

print user
print password
print path

# initialize the camera and grab a reference to the
# camera capture
camera = PiCamera()
camera.resolution = tuple(conf["resolution"])
camera.framerate = conf["fps"]
rawCapture = PiRGBArray(camera, size=tuple(conf["resolution"]))

# start and initialize camera, initialize last upload time, 
print "[INFO] warming up..."
time.sleep(conf["camera_warmup_time"])
avg = None
lastUploaded = datetime.datetime.now()
motionCounter = 0

# capture frames from the camera
for f in camera.capture_continuous(rawCapture, format="bgr", use_video_port=True):
	# grab the raw NumPy array representing the image and initialize
	# the timestamp and occupied/unoccupied text
	frame = f.array
	timestamp = datetime.datetime.now()
	text = "Unoccupied"

	# resize the frame, convert it to grayscale, and blur it
	frame = imutils.resize(frame, width=500)
	gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
	gray = cv2.GaussianBlur(gray, (21, 21), 0)

	# if the average frame is None, initialize it
	if avg is None:
		print "[INFO] starting background model..."
		avg = gray.copy().astype("float")
		rawCapture.truncate(0)
		continue

	# accumulate the weighted average between the current frame and
	# previous frames, then compute the difference between the current
	# frame and running average
	cv2.accumulateWeighted(gray, avg, 0.5)
	frameDelta = cv2.absdiff(gray, cv2.convertScaleAbs(avg))

	# threshold the delta image, dilate the thresholded image to fill
	# in holes, then find contours on thresholded image
	thresh = cv2.threshold(frameDelta, conf["delta_thresh"], 255,
		cv2.THRESH_BINARY)[1]
	thresh = cv2.dilate(thresh, None, iterations=2)
	(cnts, _) = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL,
		cv2.CHAIN_APPROX_SIMPLE)

	# loop over the contours
	for c in cnts:
		# if the contour is too small, ignore it
		if cv2.contourArea(c) < conf["min_area"]:
			continue

		# compute the bounding box for the contour, draw it on the frame,
		# and update the text
		(x, y, w, h) = cv2.boundingRect(c)
		cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
		text = "Occupied"

	# draw the text and timestamp on frame
	ts = timestamp.strftime("%A %d %B %Y %I:%M:%S%p")
	cv2.putText(frame, "Room Status: {}".format(text), (10, 20),
		cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
	cv2.putText(frame, ts, (10, frame.shape[0] - 10), cv2.FONT_HERSHEY_SIMPLEX,
		0.35, (0, 0, 255), 1)

	# checkif the room is occupied
	if text == "Occupied":
		# check if enough time has passed between uploads
		if (timestamp - lastUploaded).seconds >= conf["min_upload_seconds"]:
			# increment the motion counter
			motionCounter += 1

			# check if the number of frames with consistent motion is
			# high enough
			if motionCounter >= conf["min_motion_frames"]:
				#TODO: upload image to api!!
                                apiPath = conf["api_path"]
                                t = TempImage()
                                cv2.imwrite(t.path, frame)
                                url = "http://ec2-35-160-234-54.us-west-2.compute.amazonaws.com/api/image/add/1/1"
                                payload = "-----011000010111000001101001\r\nContent-Disposition: form-data; name=\"file\"; filename=\"chicago-skyline-1000x200-nobckg-wh.png\"\r\nContent-Type: image/png\r\n\r\n\r\n-----011000010111000001101001--"
                                headers = {
                                    'content-type': "multipart/form-data;",
                                    'cache-control': "no-cache",
                                    }
                                response = requests.post(url, files={'file':open(t.path, 'rb')})
                                print "uploading image"
                                print response.text
				# update the last uploaded timestamp and reset the motion counter
				lastUploaded = timestamp
				motionCounter = 0

	# otherwise, room is not occupied...
	else:
		motionCounter = 0

	# check if the frames should be displayed to screen
	if conf["show_video"]:
		# display the feed
		cv2.imshow("Security Feed", frame)
		key = cv2.waitKey(1) & 0xFF

		# if the `q` key is pressed, break from the lop
		if key == ord("q"):
			break

	rawCapture.truncate(0)
