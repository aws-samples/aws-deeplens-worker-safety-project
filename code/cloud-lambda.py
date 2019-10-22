import json
import boto3
import time
import os

def matchPersonsAndHats(personsList, hardhatsList):

    persons = []
    hardhats = []
    personsWithHats = []

    for person in personsList:
        persons.append(person)
    for hardhat in hardhatsList:
        hardhats.append(hardhat)

    h = 0
    matched = 0
    totalHats = len(hardhats)
    while(h < totalHats):
        hardhat = hardhats[h-matched]
        totalPersons = len(persons)
        p = 0
        while(p < totalPersons):
            person = persons[p]
            if(not (hardhat['BoundingBoxCoordinates']['x2'] < person['BoundingBoxCoordinates']['x1']
                or hardhat['BoundingBoxCoordinates']['x1'] > person['BoundingBoxCoordinates']['x2']
                or hardhat['BoundingBoxCoordinates']['y4'] < person['BoundingBoxCoordinates']['y1']
                    or hardhat['BoundingBoxCoordinates']['y1'] > person['BoundingBoxCoordinates']['y4']
                )):

                personsWithHats.append({'Person' : person, 'Hardhat' : hardhat})

                del persons[p]
                del hardhats[h - matched]

                matched = matched + 1

                break
            p = p + 1
        h = h + 1

    return (personsWithHats, persons, hardhats)

def getBoundingBoxCoordinates(boundingBox, imageWidth, imageHeight):
    x1 = 0
    y1 = 0
    x2 = 0
    y2 = 0
    x3 = 0
    y3 = 0
    x4 = 0
    y4 = 0

    boxWidth = boundingBox['Width']*imageWidth
    boxHeight = boundingBox['Height']*imageHeight

    x1 = boundingBox['Left']*imageWidth
    y1 = boundingBox['Top']*imageWidth

    x2 = x1 + boxWidth
    y2 = y1

    x3 = x2
    y3 = y1 + boxHeight

    x4 = x1
    y4 = y3

    return({'x1': x1, 'y1' : y1, 'x2' : x2, 'y2' : y2, 'x3' : x3, 'y3' : y3, 'x4' : x4, 'y4' : y4})

def getPersonsAndHardhats(labelsResponse, imageWidth, imageHeight):

    persons = []
    hardhats = []

    for label in labelsResponse['Labels']:
        if label['Name'] == 'Person' and 'Instances' in label:
            for person in label['Instances']:
                    persons.append({'BoundingBox' : person['BoundingBox'], 'BoundingBoxCoordinates' : getBoundingBoxCoordinates(person['BoundingBox'], imageWidth, imageHeight), 'Confidence' : person['Confidence']})
        elif ((label['Name'] == 'Hardhat' or label['Name'] == 'Helmet') and 'Instances' in label):
            for hardhat in label['Instances']:
                hardhats.append({'BoundingBox' : hardhat['BoundingBox'], 'BoundingBoxCoordinates' : getBoundingBoxCoordinates(hardhat['BoundingBox'], imageWidth, imageHeight), 'Confidence' : hardhat['Confidence']})

    return (persons, hardhats)

def detectWorkerSafety(bucketName, imageName, imageWidth, imageHeight):

    rekognition = boto3.client('rekognition', region_name='us-east-1')
    labelsResponse = rekognition.detect_labels(
    Image={
        'S3Object': {
            'Bucket': bucketName,
            'Name': imageName,
        }
    },
    MaxLabels=20,
    MinConfidence=60)

    persons, hardhats = getPersonsAndHardhats(labelsResponse, imageWidth, imageHeight)

    return matchPersonsAndHats(persons, hardhats)

def sendMessageToIoTTopic(iotMessage):
    topicName = "worker-safety"
    if "iot_topic" in os.environ:
        topicName = os.environ['iot_topic']
    iotClient = boto3.client('iot-data', region_name='us-east-1')
    response = iotClient.publish(
            topic=topicName,
            qos=1,
            payload=json.dumps(iotMessage)
        )
    print("Send message to topic: " + topicName)

def pushToCloudWatch(name, value):
    try:
        cloudwatch = boto3.client('cloudwatch', region_name='us-east-1')
        response = cloudwatch.put_metric_data(
            Namespace='string',
            MetricData=[
                {
                    'MetricName': name,
                    'Value': value,
                    'Unit': 'Count'
                },
            ]
        )
        #print("Metric pushed: {}".format(response))
    except Exception as e:
        print("Unable to push to cloudwatch\n e: {}".format(e))
        return True

def lambda_handler(event, context):

    bucketName = event['Records'][0]['s3']['bucket']['name']
    imageName = event['Records'][0]['s3']['object']['key']
    scaleFactor = 4
    imageWidth = 2688/scaleFactor
    imageHeight = 1520/scaleFactor

    personsWithHats, personsWithoutHats, hatsWihoutPerson = detectWorkerSafety(bucketName, imageName, imageWidth, imageHeight)

    personsWithHatsCount = len(personsWithHats)
    personsWithoutHatsCount = len(personsWithoutHats)
    hatsWihoutPersonCount = len(hatsWihoutPerson)

    pushToCloudWatch('PersonsWithSafetyHat', personsWithHatsCount)
    pushToCloudWatch('PersonsWithoutSafetyHat', personsWithoutHatsCount)

    outputMessage = "Person(s): {}".format(personsWithHatsCount+personsWithoutHatsCount)
    outputMessage = outputMessage + "\nPerson(s) With Safety Hat: {}\nPerson(s) Without Safety Hat: {}".format(personsWithHatsCount, personsWithoutHatsCount)
    print(outputMessage)

    #imageUrl = "https://s3.amazonaws.com/{}/{}".format(bucketName, imageName)
    s3_client = boto3.client('s3')
    imageUrl = s3_client.generate_presigned_url('get_object', Params={'Bucket': bucketName, 'Key': imageName })
    iotMessage = {'ImageUrl' :imageUrl, 'PersonsWithHat' : personsWithHats, 'PersonsWithoutHat' : personsWithoutHats, 'Message' : outputMessage}

    sendMessageToIoTTopic(iotMessage)

    return {
        'statusCode': 200,
        'body': json.dumps(outputMessage)
    }

def localTest():
    bucketName = "ki-worker-safety"
    #imageName = "persons/11_11/4_49/1541929754_0.jpg"
    #imageName = "worker-safety/00.jpg"
    imageName = "persons/1541974066_0.jpg"
    #imageName = "persons/yard-work.jpg"

    event = {
    "Records": [
        {
          "s3": {
            "bucket": {
              "name": bucketName,
            },
            "object": {
              "key": imageName,
            }
          }
        }
      ]
    }
    lambda_handler(event, None)

#localTest()
