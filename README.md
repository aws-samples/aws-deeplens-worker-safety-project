# Worker safety with AWS DeepLens and Amazon Rekognition

Use AWS DeepLens and Amazon Rekognition to build an application that helps identify if a person at a construction site is wearing the right safety gear, in this case, a hard hat. 

## Learning Objectives of This lab
In this lab you will learn the following:
- Create and deploy object detection project to AWS DeepLens.
- Modify the AWS DeepLens object detection inference lambda function to detect persons and upload frame to Amazon S3.
- Create a Lambda function to identify persons who are not wearing safety hats.
- Analyze the results using AWS IoT , Amazon CloudWatch and a web dashboard.

## Architecture

![](arch.png)

Follow the modules below or refer to the online course to learn how to build the application in 30 minutes.

## Online Course 

[![Online Course](worker-safety-sc.png)](https://www.aws.training/learningobject/wbc?id=32077)

## Modules

### Setup IAM role for cloud Lambda function

1. Go to IAM in AWS Console at https://console.aws.amazon.com/iam
2. Click on Roles
3. Click create role
4. Under AWS service, select Lambda and click Next: Permissions
5. Under Attach permission policies
    1. search S3 and select AmazonS3FullAccess
    2. search Rekognition and select checkbox next to AmazonRekognitionReadOnlyAccess
    3. search cloudwatch and select checkbox next to CloudWatchLogsFullAccess and CloudWatchFullAccess
    4. search iot and select AWSIotDataAccess
    5. search lambda and select checkbox next to AWSLambdaFullAccess
6. Click Next: Tags and Next: Review
7. Name is “RecognizeObjectLambdaRole”
8. Click Create role


### Setup IAM role for AWS DeepLens Lambda function

1. Click create role
2. Under AWS service, select Lambda and click Next: Permissions
3. Under Attach permission policies
    1. search S3 and select AmazonS3FullAccess
    2. search lambda and select checkbox next to AWSLambdaFullAccess
4. Click Next: Tags and Next: Review
5. Name is “DeepLensInferenceLambdaRole”
6. Click Create role


### Create S3 bucket

1. Go to Amazon S3 in AWS Console at https://s3.console.aws.amazon.com/s3/
2. Click on Create bucket.
3. Under Name and region:

* Bucket name: Enter a bucket name- your name-worker-safety (example: kashif-worker-safety)
* Choose US East (N. Virginia)
* Click Next

1. Leave default values for Configure Options screen and click Next
2.  Under Set permissions, uncheck all four checkboxes. NOTE: This step would allow us to make objects in your S3 bucket public. We are doing this to reduce few steps in the module, but you should not do that for production workloads. Instead it is recommended to use S3 Pre-Signed URLs to give time limited access to objects in S3.
3. Click Next, and click Create bucket.

### Create a cloud Lambda function

1. Go to Lambda in AWS Console at https://console.aws.amazon.com/lambda/
2. Click on Create function.
3. Under Create function, Author from scratch should be selected as default.
4. Under Author from scratch:

* Name: worker-safety-cloud
* Runtime: Python 3.7
* Role: Choose and existing role
* Existing role: RecognizeObjectLambdaRole
* Click Create function

1. Under Environment variables, add a variable:

* Key: iot_topic
* Value: worker-safety-demo-cloud

1. Download [lambda.zip](./code/lambda.zip).
2. Under Function code:

* Code entry type: Upload a zip file
* Under Function package, click Upload and select the zip file you downloaded in earlier step.
* Click Save.

1. Under Add triggers, select S3.
2. Under Configure triggers:

* Bucket: Select the S3 bucket you just created in earlier step.
* Event type: Leave default Object Created (All)
* Leave defaults for Prefix and Suffix and make sure Enable trigger checkbox is checked.
* Click Add.
* Click Save on the top right to save changed to Lambda function.

### Create AWS DeepLens inference Lambda function

1. Go to Lambda in AWS Console at https://console.aws.amazon.com/lambda/.
2. Click on Create function.
3. Under Create function, select Blueprints.
4. Under Blueprints, type greengrass and hit enter to filter blueprint templates.
5. Select greengrass-hello-world and click Configure.
6. Under Basic information:

* Name: name-worker-safety-deeplens (example: kashif-worker-safety-deeplens)
* Role: Choose and existing role
* Existing role: DeepLensInferenceLambdaRole
* Click Create function.

1. Copy the code from [deeplens-lambda.py](./code/deeplens-lambda.py) and paste under Function code for the lambda function. You can find the python file in your resources section.
2. Go to line 34 and modify line below with the name of your S3 bucket created in the earlier step.

* bucket_name = "REPLACE-WITH-NAME-OF-YOUR-S3-BUCKET"

1. Click Save.
2. Click on Actions, and then "Publish new version".
3. For Version description enter: Detect person and push frame to S3 bucket. and click Publish.

### Create a AWS DeepLens project

1. Using your browser, open the AWS DeepLens console at https://console.aws.amazon.com/deeplens/.
2. Choose Projects, then choose Create new project.
3. On the Choose project type screen

* Choose Create a new blank project, and click Next.

1. On the Specify project details screen

    * Under Project information section:
        * Project name: your-user-name-worker-safety (example: kashif-worker-safety)
    * Under Project content:
        * Click on Add model, click on radio button for deeplens-object-detection and click Add model.
        * Click on Add function, click on radio button for your lambda function (example: kashif-worker-safety-deeplens) lambda function and click Add function.
* Click Create. This returns you to the Projects screen.

### Deploy the project to AWS DeepLens 

1. From DeepLens console, On the Projects screen, choose the radio button to the left of your project name, then choose Deploy to device.
2. On the Target device screen, from the list of AWS DeepLens devices, choose the radio button to the left of the device where you want to deploy this project.
3. Choose Review. This will take you to the Review and deploy screen.
    If a project is already deployed to the device, you will see a warning message "There is an existing project on this device. Do you want to replace it? If you Deploy, AWS DeepLens will remove the current project before deploying the new project."
4. On the Review and deploy screen, review your project and click Deploy to deploy the project. This will take you to to device screen, which shows the progress of your project deployment.

### View output in AWS IoT

1. Go to IoT Console at https://console.aws.amazon.com/iot/home
2. Under Subscription topic enter topic name you entered as environment variable for Lambda in earlier step (example: worker-safety-demo-cloud) and click Subscribe to topic.
3. You should now see JSON message with a list of people detected and whether they are wearing safety hats or not.

### View output in Amazon CloudWatch

* Go to CloudWatch Console at https://console.aws.amazon.com/cloudwatch
* Create a dashboard called “worker-safety-dashboard-your-name”
* Choose Line in the widget
* Under Custom Namespaces, select “string”, “Metrics with no dimensions”, and then select PersonsWithSafetyHat and PersonsWithoutSafetyHat.
* Next, set “Auto-refresh” to the smallest interval possible (1h), and change the “Period” to whatever works best for you (1 second or 5 seconds)

### View output in web dashboard

1. Go to AWS Cognito console at https://console.aws.amazon.com/cognito
2. Click on Manage Identity Pools
3. Click on Create New Identity Pool
4. Enter “awsworkersafety” for Identity pool name
5. Select Enable access to unauthenticated identities
6. We are using using Unauthenticated identity option to keep things simple in the demo. For real world application where you only want authorized users to access the app you should configure Authentication providers.
7. Click Create Pool
8. Expand View Details
9. Under: Your unauthenticated identities would like access to Cognito, expand View Policy Document and click Edit.
10. Click Ok for Edit Policy prompt.
11. Copy JSON from [cognitopolicy.json](./code/cognitopolicy.json) and paste in the text box.
12. Click Allow
13. Make note of the Identity Pool as you will need it in following steps.
14. Got to IoT in AWS Console at: https://console.aws.amazon.com/iot
15. Click on settings and make note of Endpoint, you will need this the following step.
16. Download [webdashboard.zip](./code/webdashboard.zip) and unzip on your local drive.
17. Edit aws-configuration.js and update poolId with Cognito Identity Pool Id and host with IoT EndPoint you got in earlier steps.
18. From terminal go to the root of the unzipped folder and run “npm install”
19. Next, run “./node_modules/.bin/webpack —config webpack.config.js”
20. This will create the build we can easily deploy.
21. Go to S3 bucket, and create a folder web
22. From web folder in S3 bucket click upload and select bundle.js, index.html and style.css.
23. From Set permission, Choose Grant public read access to the objects. and click Next
24. Leave default settings for following screens and click upload.
25. Click on index.html and click on the link to open the web page in browser.
26. In the address URL append ?iottopic=NAME-OF-YOUR-IOT-TOPIC. This is the same value you added to Lambda environment variable and hit Enter.
27. You should now see images coming from DeepLens with a green or red box around the person.


## Clean up
Delete Lambda functions, S3 bucket and IAM roles.

## License Summary

This sample code is made available under the MIT-0 license. See the LICENSE file.
