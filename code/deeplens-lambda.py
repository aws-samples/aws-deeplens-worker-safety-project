#*****************************************************
#                                                    *
# Copyright 2018 Amazon.com, Inc. or its affiliates. *
# All Rights Reserved.                               *
#                                                    *
#*****************************************************
""" A sample lambda for object detection"""
from threading import Thread, Event
import os
import json
import numpy as np
import awscam
import cv2
import greengrasssdk
import time
import base64
import urllib
import zipfile
import sys
import datetime

#boto3 is not installed on device by default.

boto_dir = '/tmp/boto_dir'
if not os.path.exists(boto_dir):
    os.mkdir(boto_dir)
urllib.urlretrieve("https://s3.amazonaws.com/dear-demo/boto_3_dist.zip", "/tmp/boto_3_dist.zip")
with zipfile.ZipFile("/tmp/boto_3_dist.zip", "r") as zip_ref:
    zip_ref.extractall(boto_dir)
sys.path.append(boto_dir)

import boto3

bucket_name = "REPLACE-WITH-NAME-OF-YOUR-S3-BUCKET"

# Create an IoT client for sending to messages to the cloud.
client = greengrasssdk.client('iot-data')
iot_topic = '$aws/things/{}/infer'.format(os.environ['AWS_IOT_THING_NAME'])

class LocalDisplay(Thread):
    """ Class for facilitating the local display of inference results
        (as images). The class is designed to run on its own thread. In
        particular the class dumps the inference results into a FIFO
        located in the tmp directory (which lambda has access to). The
        results can be rendered using mplayer by typing:
        mplayer -demuxer lavf -lavfdopts format=mjpeg:probesize=32 /tmp/results.mjpeg
    """
    def __init__(self, resolution):
        """ resolution - Desired resolution of the project stream """
        # Initialize the base class, so that the object can run on its own
        # thread.
        super(LocalDisplay, self).__init__()
        # List of valid resolutions
        RESOLUTION = {'1080p' : (1920, 1080), '720p' : (1280, 720), '480p' : (858, 480)}
        if resolution not in RESOLUTION:
            raise Exception("Invalid resolution")
        self.resolution = RESOLUTION[resolution]
        # Initialize the default image to be a white canvas. Clients
        # will update the image when ready.
        self.frame = cv2.imencode('.jpg', 255*np.ones([640, 480, 3]))[1]
        self.stop_request = Event()

    def run(self):
        """ Overridden method that continually dumps images to the desired
            FIFO file.
        """
        # Path to the FIFO file. The lambda only has permissions to the tmp
        # directory. Pointing to a FIFO file in another directory
        # will cause the lambda to crash.
        result_path = '/tmp/results.mjpeg'
        # Create the FIFO file if it doesn't exist.
        if not os.path.exists(result_path):
            os.mkfifo(result_path)
        # This call will block until a consumer is available
        with open(result_path, 'w') as fifo_file:
            while not self.stop_request.isSet():
                try:
                    # Write the data to the FIFO file. This call will block
                    # meaning the code will come to a halt here until a consumer
                    # is available.
                    fifo_file.write(self.frame.tobytes())
                except IOError:
                    continue

    def set_frame_data(self, frame):
        """ Method updates the image data. This currently encodes the
            numpy array to jpg but can be modified to support other encodings.
            frame - Numpy array containing the image data of the next frame
                    in the project stream.
        """
        ret, jpeg = cv2.imencode('.jpg', cv2.resize(frame, self.resolution))
        if not ret:
            raise Exception('Failed to set frame data')
        self.frame = jpeg

    def join(self):
        self.stop_request.set()

def push_to_s3(img):
    try:
        index = 0

        timestamp = int(time.time())
        now = datetime.datetime.now()
        key = "persons/{}_{}/{}_{}/{}_{}.jpg".format(now.month, now.day,
                                                   now.hour, now.minute,
                                                   timestamp, index)

        s3 = boto3.client('s3')

        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 90]
        _, jpg_data = cv2.imencode('.jpg', img, encode_param)
        response = s3.put_object(ACL='private',
                                 Body=jpg_data.tostring(),
                                 Bucket=bucket_name,
                                 Key=key)

        client.publish(topic=iot_topic, payload="Response: {}".format(response))
        client.publish(topic=iot_topic, payload="Frame pushed to S3")
    except Exception as e:
        msg = "Pushing to S3 failed: " + str(e)
        client.publish(topic=iot_topic, payload=msg)


def greengrass_infinite_infer_run():
    """ Entry point of the lambda function"""
    try:
        # This object detection model is implemented as single shot detector (ssd), since
        # the number of labels is small we create a dictionary that will help us convert
        # the machine labels to human readable labels.
        model_type = 'ssd'
        output_map = {1: 'aeroplane', 2: 'bicycle', 3: 'bird', 4: 'boat', 5: 'bottle', 6: 'bus',
                      7 : 'car', 8 : 'cat', 9 : 'chair', 10 : 'cow', 11 : 'dinning table',
                      12 : 'dog', 13 : 'horse', 14 : 'motorbike', 15 : 'person',
                      16 : 'pottedplant', 17 : 'sheep', 18 : 'sofa', 19 : 'train',
                      20 : 'tvmonitor'}
        # Create an IoT client for sending to messages to the cloud.
        ###client = greengrasssdk.client('iot-data')
        ###iot_topic = '$aws/things/{}/infer'.format(os.environ['AWS_IOT_THING_NAME'])
        # Create a local display instance that will dump the image bytes to a FIFO
        # file that the image can be rendered locally.
        local_display = LocalDisplay('480p')
        local_display.start()
        # The sample projects come with optimized artifacts, hence only the artifact
        # path is required.
        model_path = '/opt/awscam/artifacts/mxnet_deploy_ssd_resnet50_300_FP16_FUSED.xml'
        # Load the model onto the GPU.
        client.publish(topic=iot_topic, payload='Loading object detection model')
        model = awscam.Model(model_path, {'GPU': 1})
        client.publish(topic=iot_topic, payload='Object detection model loaded')
        # Set the threshold for detection
        detection_threshold = 0.25
        # The height and width of the training set images
        input_height = 300
        input_width = 300
        # Do inference until the lambda is killed.
        while True:
            detectedPerson = False
            # Get a frame from the video stream
            ret, frame = awscam.getLastFrame()
            if not ret:
                raise Exception('Failed to get frame from the stream')
            # Resize frame to the same size as the training set.
            frame_resize = cv2.resize(frame, (input_height, input_width))
            # Run the images through the inference engine and parse the results using
            # the parser API, note it is possible to get the output of doInference
            # and do the parsing manually, but since it is a ssd model,
            # a simple API is provided.
            parsed_inference_results = model.parseResult(model_type,
                                                         model.doInference(frame_resize))
            # Compute the scale in order to draw bounding boxes on the full resolution
            # image.
            yscale = float(frame.shape[0]/input_height)
            xscale = float(frame.shape[1]/input_width)
            # Dictionary to be filled with labels and probabilities for MQTT
            cloud_output = {}
            # Get the detected objects and probabilities
            detectedPerson = False
            for obj in parsed_inference_results[model_type]:
                if obj['prob'] > detection_threshold:
                    if(output_map[obj['label']] == 'person'):
                        detectedPerson = True
                        break

            if(detectedPerson):
                rfr = cv2.resize(frame, (672, 380))
                push_to_s3(rfr)
                #fr2 = cv2.resize(frame, (1344, 760))
                #_, jpg_data = cv2.imencode('.jpg', fr2)
                #push_to_s3(jpg_data)

            for obj in parsed_inference_results[model_type]:
                if obj['prob'] > detection_threshold:

                    if(output_map[obj['label']] == 'person'):
                        detectedPerson = True

                    # Add bounding boxes to full resolution frame
                    xmin = int(xscale * obj['xmin']) \
                           + int((obj['xmin'] - input_width/2) + input_width/2)
                    ymin = int(yscale * obj['ymin'])
                    xmax = int(xscale * obj['xmax']) \
                           + int((obj['xmax'] - input_width/2) + input_width/2)
                    ymax = int(yscale * obj['ymax'])

                    # See https://docs.opencv.org/3.4.1/d6/d6e/group__imgproc__draw.html
                    # for more information about the cv2.rectangle method.
                    # Method signature: image, point1, point2, color, and tickness.
                    cv2.rectangle(frame, (xmin, ymin), (xmax, ymax), (255, 165, 20), 10)
                    # Amount to offset the label/probability text above the bounding box.
                    text_offset = 15
                    # See https://docs.opencv.org/3.4.1/d6/d6e/group__imgproc__draw.html
                    # for more information about the cv2.putText method.
                    # Method signature: image, text, origin, font face, font scale, color,
                    # and tickness
                    cv2.putText(frame, "{}: {:.2f}%".format(output_map[obj['label']],
                                                               obj['prob'] * 100),
                                (xmin, ymin-text_offset),
                                cv2.FONT_HERSHEY_SIMPLEX, 2.5, (255, 165, 20), 6)
                    # Store label and probability to send to cloud
                    cloud_output[output_map[obj['label']]] = obj['prob']

            # Set the next frame in the local display stream.
            local_display.set_frame_data(frame)
            # Send results to the cloud
            client.publish(topic=iot_topic, payload=json.dumps(cloud_output))
    except Exception as ex:
        client.publish(topic=iot_topic, payload='Error in object detection lambda: {}'.format(ex))

greengrass_infinite_infer_run()
