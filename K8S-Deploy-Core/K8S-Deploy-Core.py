import json
import sys
import os
import logging
from datetime import datetime
from pprint import pprint, pformat
from kubernetes import client, config
from kubernetes.client.rest import ApiException
from kubernetes.stream import stream
from urllib2 import urlopen
import base64
import tempfile
import socket
import yaml
import time
import io
import itertools as it
from github3 import login
from github3 import authorize
import random
import string

from enum import Enum

_git_user_login = None


gitusername = ''

gituserpassword = ''

gitcredsfile = ''

gitpath = ''

gitrepo = ''

apik8suser = ''

apik8screds = ''

apik8scert = ''

_api_user_str = ''

_api_key_str = ''

_download_key_str = ''

_api_key_url = ''

_api_host_ssl = 'https'

_api_host_no_ssl = 'http'

_api_host_name = ''

_api_port_str = '443'

_api_bearer_str = 'Bearer'

_api_ca_cert_url = ''

_download_ca_cert_str = ''

_api_ca_cert = ''

_api_host_str = ''

_api_bearer_token = _api_bearer_str + ' ' + _api_key_str

_deploy = False

_service = False

_has_volume = False

_has_secret = False

_has_vault = False

_has_stateful = False

_has_config = False


class Status(Enum):
        Fail = 0
        Success = 1
        Initializing = 2
        InProgress = 3


class Resource(Enum):
        K8SObject = 0
        Deployment = 1
        Service = 2
        Volume = 3
        Secret = 4
        Stateful = 5
        Config = 6


_current_status = Status.Initializing

_current_resource = Resource.K8SObject

_current_status_msg = 'Initializing k8s deploy object...'

########################################################################################
#  K8S_Shell_AWS Package mpw version 2.0 build 2.0.19
#  There are some scripts that run from Python shell Linux/Windows command line
#  But mainly this is K8S and Openshift API
#  Next step is to move it to a Driver Interface to a TOSCA Oasis standard driver set
#
#  Disclaimer - Currently this has only been tested on Ubuntu 17 command line
#     Use at own Risk, this package only works on AWS so far
#      Future versions will work on GKE
#    Prerequisites
#       Install Kubernetes- both kops and kubectl are required to be working and
#       configured from the command line
#        Install AWS Client - need AWS client configured to access your AWS Account
#     There is a mixing of some Docker concepts here as we perform Docker build and
#     Deployments to Kubernetes pods for Docker built applications
#     Some Docker examples are provided
#     The broader goal is to move the Docker build and deployments to an App based
#     TOSCA Shell thus having a cloud provider Shell and a Docker App Deployment Shell
#
########################################################################################


class K8S_APP_Shell_OS(object):
    """
    K8S_App_Shell_OS.py
    #  Package mpw v2.0.6 production build
    #  uses the attributes in JSON file to buildout and teardown cluster
    #  and deploy container apps and execute commands on container
    """
    _status_obj = []
    _k8s_app_data = dict()
    _data_file_name = "K8S_App_Data_OS.json"
    _loggerON = "True"
    _config_file_load = 'False'

    def __init__(self, data):
        pass

    def _create_secret_vault(self):
        secret_vault = find_secret(self, 'secret-vault')
        if not secret_vault:
            self._create_user_secret(self.AppNamespace)
            secret_pod = find_pod(self, 'secret-pod')
            if not secret_pod
                self._create_secret_pod(self.AppNamespace))
        pass

    @staticmethod
    def _base64(basestr):
        """
        conversion to Base64 for secret vault
        :param basestr
        :return:
        """
        return base64.encodestring(basestr.encode()).decode()

    @staticmethod
    def _decode_base64(basestr):
        """
        conversion to Base64 for secret vault
        :param basestr
        :return:
        """
        return basestr.decode()

    @staticmethod
    def _isBase64(basestr):
        """
        is a string base 64 encoded
        :param basestr:
        :return:
        """
        try:
            if base64.b64encode(base64.b64decode(basestr)) == basestr:
                return True
        except BaseException:
            pass
            return False

    def _create_kube_config_from_inputs(self, api_key, api_host, api_port, api_ca):
        """
        Get kube config from user inputs
        and instantiate kube api extensions client
        :param api_key:
        :param api_host:
        :param api_port:
        :param api_ca:
        :return:
        """
        # instantiate client config object
        configuration = client.Configuration()
        # add user kubernetes attributes
        configuration.host = self._get_host_name(api_host, api_port)
        configuration.api_key['authorization'] = self._get__bearer_token(api_key)
        configuration.ssl_ca_cert = self._get_ca_cert_filename(api_ca)
        if self._loggerON == 'True':
            configuration.debug = True
        # check authorization for API calls
        self.core_api_instance = client.CoreV1Api(client.ApiClient(configuration))
        api_instance = client.AuthorizationV1beta1Api(client.ApiClient(configuration))
        try:
            api_response = api_instance.get_api_resources()
            logging.debug('Successful API response: ' + pformat(api_response))
            pprint(api_response)
        except ApiException as e:
            print("Exception when calling AuthorizationV1beta1Api->get_api_resources: %s\n" % e)
        extensions_client = client.ExtensionsV1beta1Api(client.ApiClient(configuration))
        return extensions_client

    def _create_os_config_from_inputs(self, api_key, api_host, api_port, api_ca):
        """
         Create Openshift Client config from inputted values
        :param api_key:
        :param api_host:
        :param api_port:
        :param api_ca:
        :return:
        """
        from openshift import client
        oclient_config = client.Configuration()
        oclient_config.host = self._get_host_name(api_host, api_port)
        oclient_config.api_key['authorization'] = self._get__bearer_token(api_key)
        oclient_config.ssl_ca_cert = self._get_ca_cert_filename(api_ca)
        # add user kubernetes attributes
        oapi = client.OapiApi(oclient_config)
        return oapi

    def _get_kube_config_from_file(self):
        """
        Get kube config from ~.kube/config or alternative file
        and instantiate kube api extensions client
        :return:
        """
        # load configuration from kube config file
        config.load_kube_config()
        # load extensions client
        extensions_client = client.ExtensionsV1beta1Api()
        # print attributes for kubernetes
        if self._loggerON == 'True':
            extensions_client.api_client.configuration.debug = True
        return extensions_client

    def _create_user_secret(self, app_namespace):
        """
        create a secret for username and password
        :param app_namespace:
        :return:
        """
        self._current_status = Status.InProgress
        self._current_resource = Resource.Secret
        self._current_status_msg = 'Creating K8S Token Secret...'
        secret = client.V1Secret()
        secret.metadata = client.V1ObjectMeta(name="secret-vault")
        secret.type = "Opaque"
        secret.data = {"username": self._api_user_str_b64, "password": self._api_key_str_b64}
        try:
            api_response = self.core_api_instance.create_namespaced_secret(namespace=app_namespace, body=secret)
            pprint(api_response)
            self._current_status = Status.Success
            self._current_resource = Resource.Secret
            self._current_status_msg = 'Creating K8S Token Secret...'
        except ApiException as e:
            print("Exception when CoreK8sApi->create_namespaced_secret %s\n" % e)
            self._current_status = Status.Fail
            self._current_resource = Resource.Secret
            self._current_status_msg = 'Creating K8S Token Secret...'
        pass

    def _create_secret_pod(self, app_namespace):
        """
        create a secret pod for username and password
        :param app_namespace:
        :return:
        """
        container = client.V1Container(
            name="secret-container",
            image="busybox",
            command=['sleep', '3600'],
            volume_mounts=[client.V1VolumeMount(mount_path="/data/busybox", name="secret-vol")],
            ports=[client.V1ContainerPort(container_port=8080)])
        spec = client.V1PodSpec(volumes=[client.V1Volume(name="secret-vol")],
                                containers=[container])
        spec.volumes[0].secret = client.V1SecretVolumeSource(secret_name="secret-vault")
        pod = client.V1Pod()
        pod.metadata = client.V1ObjectMeta(name="secret-pod")
        pod.spec = spec
        self._current_status = Status.InProgress
        self._current_resource = Resource.Secret
        self._current_status_msg = 'Creating Secret Vault...'
        try:
            api_response = self.core_api_instance.create_namespaced_pod(namespace=app_namespace, body=pod)
            pprint(api_response)
            self._current_status = Status.Success
            self._current_resource = Resource.Secret
            self._current_status_msg = 'Creating Secret Vault...'
            self._has_Vault = True
        except ApiException as e:
            print("Exception when CoreK8sApi->create_namespaced_pod %s\n" % e)
            self._current_status = Status.Success
            self._current_resource = Resource.Secret
            self._current_status_msg = 'Creating Secret Vault...'
        pass

    @staticmethod
    def _get_host_name(host, port):
        """
        Ensure host name URI port is in right format
        :param host:
        :param port:
        :return:
        """
        if not host or not port:
            api_host_name = _api_host_str
        else:
            api_host_name = _api_host_ssl + '://' + host + ':' + port
        return api_host_name

    @staticmethod
    def _resolve_host_name(host_name):
        """
        Resolve the host name via socket call
        :param host_name:
        :return:
        """
        try:
            socket.gethostbyname(host_name)
        except socket.error as e:
            print("Error: Host " + host_name + " does not appear to exist", e)
            logging.error("Error: Host " + host_name + " does not appear to exist", e)

    def _load_app_attr(self, data_dict):
        """
        Loads user inputted attributes for application
        :param data_dict:
        :return:
        """
        self._k8s_app_data = data_dict
        self.AppType = data_dict["AppType"]
        self.AppName = data_dict["AppName"]
        self.AppSubType = data_dict["AppSubType"]
        self.AppNamespace = data_dict["AppNamespace"]
        self.AppSvcName = data_dict["AppSvcName"]
        if self.AppType == 'dict':
            if self.AppSubType == 'app':
                self.AppImg = data_dict["AppImg"]
                self.AppDeployName = data_dict["AppDeployName"]
                self.AppPort = data_dict["AppPort"]
                self.AppRepl = data_dict["AppRepl"]
            elif self.AppSubType == 'pod':
                self.AppImg = data_dict["AppImg"]
            try:
                self.AppImgUpdate = data_dict["AppImgUpdate"]
            except KeyError as e:
                self.AppImgUpdate = ""
                print("Error: Image Update does not appear to exist.", e)
                logging.error("Image Update does not appear to exist.", e)
        else:
            if self.AppType == 'yaml':
                self.AppYamlFileName = data_dict["AppYamlFileName"]
                self.AppImg = " "
                self.AppDeployName = data_dict["AppDeployName"]
                self.AppPort = " "
                self.AppRepl = " "
                self.gitusername = data_dict["gitusername"]
                self.gituserpassword = data_dict["gituserpassword"]
                self.gitcredsfile = data_dict["gitcredsfile"]
                self.gitpath = data_dict["gitpath"]
                self.gitrepo = data_dict["gitrepo"]
                self.apik8suser = data_dict["apik8suserstr"]
                self.apik8screds = data_dict["apik8screds"]
                self.apik8scert = data_dict["apik8scert"]
        pass

    def _init_data_from_json_file(self):
        """
        Loads application attributes from JSON file
        :return:
        """
        try:
            self.data_dict = json.load(open(self._data_file_name))
        except IOError as e:
            print("Error: File K8S_App_Data_OS.json does not appear to exist.", e)
            logging.error("File K8S_App_Data_OS.json does not appear to exist.", e)
        # app attributes
        self._load_app_attr(self.data_dict)
        return self.data_dict

    def _get_current_status(self, svc_obj, pod_obj, secret_obj, volume_obj):
        """
        creates a status object and stores all failure or success messages
        :param svc_obj:
        :param pod_obj:
        :param secret_obj:
        :param volume_obj:
        :return:
        """
        self._current_status = "In Progress"
        self._current_resource = Resource.K8SObject
        self._current_status_msg = 'Creating Status Object...'
        if not svc_obj:
            self._current_status = "Fail"
            self._current_resource = "Service"
            self._current_status_msg = 'Failure in Service Endpoint Creation...'
            self._status_obj.append(self._current_status)
            self._status_obj.append(self._current_resource)
            self._status_obj.append(self._current_status_msg)
        if not pod_obj:
            self._current_status = "Fail"
            self._current_resource = "Pod"
            self._current_status_msg = 'Failure in Deployment Pod creation...'
            self._status_obj.append(self._current_status)
            self._status_obj.append(self._current_resource)
            self._status_obj.append(self._current_status_msg)
        if not secret_obj:
            self._current_status = "Fail"
            self._current_resource = "Secret"
            self._current_status_msg = 'Failure in Creation of Secret Vault...'
            self._status_obj.append(self._current_status)
            self._status_obj.append(self._current_resource)
            self._status_obj.append(self._current_status_msg)
        if volume_obj and ('Bound' not in volume_obj[0]):
            self._current_status = "Fail"
            self._current_resource = "Volume"
            self._current_status_msg = 'Failure in Creation and attachment of Volume...'
            self._status_obj.append(self._current_status)
            self._status_obj.append(self._current_resource)
            self._status_obj.append(self._current_status_msg)
        if self._current_status == "In Progress":
            self._current_status = "Success"
            self._current_resource = "K8S Object"
            self._current_status_msg = 'Status Object Complete...'
            self._status_obj.append(self._current_status)
            self._status_obj.append(self._current_resource)
            self._status_obj.append(self._current_status_msg)
        return self._status_obj

    def _start_logger(self):
        """
        start the logger function
        :return:
        """
        logger_file_name = datetime.now().strftime('k8s_app_os_shell_%H_%M_%d_%m_%Y.log')
        logging.basicConfig(filename=logger_file_name, format='%(asctime)s %(message)s', level=logging.DEBUG)
        logging.info("Started Logging for DEBUG in file location: k8s_app_shell.log")
        working_dir = os.path.dirname(sys.argv[0])
        self.master_package_dir = os.path.abspath(working_dir)
        logging.info("Package master directory location: " + self.master_package_dir)
        self.master_log_dir = logging.getLoggerClass().root.handlers[0].baseFilename
        logging.info("Logging for DEBUG in file path: " + self.master_log_dir)
        pass

    def shell_teardown_script(self, app_deploy_name, app_namespace, app_svcname):
        """
         Teardown all apps and resources
        :param app_deploy_name:
        :param app_namespace:
        :param app_svcname
        :return:
        """
        delete_deployment(self.extensions_v1beta1, app_deploy_name, app_namespace)
        delete_service(self.core_api_instance, app_svcname, app_namespace)
        secret_vault = find_secret(self, 'secret-vault')
        logging.debug('secret vault found: ' + pformat(secret_vault))
        secret_pod = find_pod(self, 'secret-pod')
        print('secret pod found: ' + pformat(secret_pod))
        if secret_vault and secret_pod:
            self._delete_user_vault(app_namespace)
        pass

    def shell_startup_script(self):
        """
        perform startup on k8s cluster
        :return:
        """
        # project = find_project(self)
        # print('project found: ', project)
        pass

    def shell_health_check_script(self, app_name, app_namespace, app_svc_name):
        """
        Provides deployment resource and all subresources pods, secrets, volumes
        :param app_name:
        :param app_namespace:
        :param app_svc_name:
        :return:
        """
        svc_endp_list = get_svc_endpoints(self, app_namespace, app_svc_name)
        self.svc_obj = get_addr_port_list(svc_endp_list, app_svc_name)
        self.pod_obj = get_pod_object(self, app_name)
        self.secret_obj = get_secrets_list_for_deployment(self, app_name)
        self.volume_obj = get_volume_list_for_deployment(self, app_name)
        self._current_status = Status.InProgress
        self._current_resource = Resource.K8SObject
        self._current_status_msg = 'Initialization Complete...'
        self._status_obj = self._get_current_status(self.svc_obj, self.pod_obj, self.secret_obj, self.volume_obj)
        return {"Status": self._status_obj, "Pods": self.pod_obj, "Endpoints": self.svc_obj, "Secrets": self.secret_obj,
                "Volumes": self.volume_obj}

    def shell_deployment_script(self, app_name, app_port, app_image, app_type, app_repl,
                                app_deploy_name, app_namespace, app_img_update,
                                app_yaml_file_name, app_sub_type, app_svc_name):
        """
        Deploy the application and print all namespaces, projects and pods
        :param app_name:
        :param app_port:
        :param app_image:
        :param app_type:
        :param app_repl:
        :param app_deploy_name:
        :param app_namespace:
        :param app_img_update:
        :param app_yaml_file_name:
        :param app_sub_type:
        :param app_svc_name:
        :return:
        """
        # project = find_project(self)
        # print('project found: ', project)
        # if not project:
        #   create_project_dict(self, app_namespace)
        self.svc_obj = None
        self.svc_status_obj = None
        if app_type == 'dict':
            if app_sub_type == 'app':
                deployment = create_deployment_object(app_name, app_port, app_image, app_type, app_repl,
                                                      app_deploy_name)
                pprint(deployment)
                create_deployment(self.extensions_v1beta1, deployment, app_namespace)
                if not len(app_img_update) == 0:
                    update_deployment(self.extensions_v1beta1, deployment, app_img_update, app_deploy_name,
                                      app_namespace)
                svc_yaml_file_name = app_svc_name + ".yaml"
                create_svc_file(self.core_api_instance, svc_yaml_file_name, app_namespace)
                time.sleep(30)
                # self.svc_obj = get_svc_endpoints(self, app_namespace, app_svc_name)
                self.svc_obj = None
        else:
            if app_type == 'yaml':
                if app_sub_type == 'app':
                    self.svc_status_obj = split_yaml_file(self, app_name, app_yaml_file_name, app_svc_name,
                                                          app_namespace)
        return self.svc_status_obj


############################################################################################################
#
# K8S API calls to deploy and undeploy K8S apps based on Deployment Object and App Attributes
#
############################################################################################################


def k8s_yaml_to_dict_helper(yaml_file_name):
    """
    Create a dictionary from a yaml file
    :param yaml_file_name:
    :return:
    """
    # if os.name == 'nt':
    # temp_dir_name = 'c:\\temp\\'
    # else:
    temp_dir_name = '__main__'
    with open(os.path.join(os.path.dirname(temp_dir_name), yaml_file_name)) as f:
        data_loaded = yaml.load(f)
    pprint(data_loaded)
    return data_loaded


def split_yaml_file(self, app_name, app_yaml_file_url, app_svc_name, app_namespace):
    logging.debug("In Init, Calling routine: " + sys._getframe().f_back.f_code.co_name)
    base = app_name
    vol_yaml_file_name = base + '-volume.yaml'
    svc_yaml_file_name = base + '-service.yaml'
    deploy_yaml_file_name = base + '-deploy.yaml'

    f = urlopen(app_yaml_file_url)
    for key, group in it.groupby(f, lambda line: line.startswith('---')):
        if not key:
            group = list(group)
            if any('Deployment' in s for s in group):
                with open(deploy_yaml_file_name, 'w') as de:
                    for item in group:
                        self._hasDeploy = True
                        de.write("%s" % item)
                    de.close()
            elif any('Service' in s for s in group):
                with open(svc_yaml_file_name, 'w') as sv:
                    for item in group:
                        self._hasService = True
                        sv.write("%s" % item)
                    sv.close()
            elif any('PersistentVolumeClaim'in s for s in group):
                with open(vol_yaml_file_name, 'w') as vc:
                    for item in group:
                        self._hasVolume = True
                        vc.write("%s" % item)
                    vc.close()

    if os.path.isfile(vol_yaml_file_name):
        create_persistent_volume(self, self.core_api_instance, vol_yaml_file_name, app_namespace)
    create_deployment_file(self, self.extensions_v1beta1, deploy_yaml_file_name, app_namespace)
    if os.path.isfile(svc_yaml_file_name):
        create_svc_file(self, self.core_api_instance, svc_yaml_file_name, app_namespace)
        time.sleep(60)
        self._current_status = Status.InProgress
        self._current_resource = Resource.K8SObject
        self._current_status_msg = 'Performing Health Check...'
        svc_endp_list = get_svc_endpoints(self, app_namespace, app_svc_name)
        self.svc_obj = get_addr_port_list(svc_endp_list, app_svc_name)
        self.pod_obj = get_pod_object(self, app_name)
        self.secret_obj = get_secrets_list_for_deployment(self, app_name)
        self.volume_obj = get_volume_list_for_deployment(self, app_name)
        self._current_status = Status.Initializing
        self._current_resource = Resource.K8SObject
        self._current_status_msg = 'Completing Health Check...'
        self._status_obj = self._get_current_status(self.svc_obj, self.pod_obj, self.secret_obj, self.volume_obj)
        return {"Status": self._status_obj, "Pods": self.pod_obj, "Endpoints": self.svc_obj, "Secrets": self.secret_obj,
                "Volumes": self.volume_obj}
    pass


def k8s_dict_to_yaml_helper(data_dict, yaml_file_name):
    """
    Helper file to create YAML file from dictionary
    :param data_dict:
    :param yaml_file_name:
    :return:
    """
    with io.open(yaml_file_name, 'w', encoding='utf8') as outfile:
        yaml.dump(data_dict, outfile, default_flow_style=False, allow_unicode=True)
    pass


def create_deployment_file(self, api_instance, yaml_file_name, app_namespace):
    """
    Create deployment from YAML File
    :param self:
    :param api_instance:
    :param yaml_file_name:
    :param app_namespace:
    :return deployment:
    """
    self._current_status = Status.InProgress
    self._current_resource = Resource.Deployment
    self._current_status_msg = 'Creating Deployment...'
    deployment = k8s_yaml_to_dict_helper(yaml_file_name)
    os.remove(yaml_file_name)
    try:
        api_response = api_instance.create_namespaced_deployment(
            body=deployment,
            namespace=app_namespace)
        print("Deployment created. status='%s'" % str(api_response.status))
        self._current_status = Status.Success
        self._current_resource = Resource.Deployment
        self._current_status_msg = 'Creating Deployment...'
    except ApiException as e:
        print("Deployment failed. status='%s'" % e)
        logging.error("Deployment failed. status='%s'" % e)
        self._current_status = Status.Fail
        self._current_resource = Resource.Deployment
        self._current_status_msg = 'Creating Deployment...'
    return deployment


def create_persistent_volume(self, api_instance, yaml_file_name, app_namespace):
    """
    Create persistent volume claim from YAML file
    :param self:
    :param api_instance:
    :param yaml_file_name:
    :param app_namespace:
    :return:
    """
    self._current_status = Status.InProgress
    self._current_resource = Resource.Volume
    self._current_status_msg = 'Attaching Volume...'
    pvc = k8s_yaml_to_dict_helper(yaml_file_name)
    os.remove(yaml_file_name)
    try:
        api_response = api_instance.create_namespaced_persistent_volume_claim(
            body=pvc,
            namespace=app_namespace)
        pprint(api_response)
        self._current_status = Status.Success
        self._current_resource = Resource.Volume
        self._current_status_msg = 'Attaching Volume...'
    except ApiException as e:
        print("Exception when calling CoreV1Api->create_namespaced_persistent_volume_claim: %s\n" % e)
        self._current_status = Status.Fail
        self._current_resource = Resource.Volume
        self._current_status_msg = 'Attaching Volume...'
    pass


def create_deployment_dict(api_instance, deployment_dict, app_namespace):
    """
    Create deployment from dictionary dta structure
    :param api_instance:
    :param deployment_dict:
    :param app_namespace:
    :return deployment:
    """
    pprint("Dictionary deployment: ", deployment_dict)
    try:
        api_response = api_instance.create_namespaced_deployment(
            body=deployment_dict,
            namespace=app_namespace)
        print("Deployment created. status='%s'" % str(api_response.status))
    except ApiException as e:
        print("Deployment failed. status='%s'" % e)
        logging.error("Deployment failed. status='%s'" % e)
    return deployment_dict


def create_rs_file(api_instance, yaml_file_name, app_namespace):
    """
    Create deployment from YAML File
    :param api_instance:
    :param yaml_file_name:
    :param app_namespace:
    :return deployment:
    """
    rs_deployment = k8s_yaml_to_dict_helper(yaml_file_name)
    try:
        api_response = api_instance.create_namespaced_replica_set(
            body=rs_deployment,
            namespace=app_namespace)
        print("Replica set created. status='%s'" % str(api_response.status))
    except ApiException as e:
        print("Replicaset creation failed. status='%s'" % e)
        logging.error("Replicaset creation failed. status='%s'" % e)
    return rs_deployment


def create_svc_file(self, api_instance, yaml_file_name, app_namespace):
    """
    Create deployment from YAML File
    :param self:
    :param api_instance:
    :param yaml_file_name:
    :param app_namespace:
    :return deployment:
    """
    self._current_status = Status.InProgress
    self._current_resource = Resource.Service
    self._current_status_msg = 'Deploying Service..'
    svc_deployment = k8s_yaml_to_dict_helper(yaml_file_name)
    os.remove(yaml_file_name)
    try:
        api_response = api_instance.create_namespaced_service(
            body=svc_deployment,
            namespace=app_namespace)
        print("Service created. status='%s'" % str(api_response.status))
        self._current_status = Status.Success
        self._current_resource = Resource.Service
        self._current_status_msg = 'Deploying Service..'
    except ApiException as e:
        print("Service creation failed. status='%s'" % e)
        logging.error("Service creation failed. status='%s'" % e)
        self._current_status = Status.Fail
        self._current_resource = Resource.Service
        self._current_status_msg = 'Deploying Service..'
    return svc_deployment


def create_deployment_object(app_name, app_port, app_img, app_type, app_repl, app_deploy_name):
    """
    Create a k8s deployment object based on app parameters using k8s api
    :param app_name:
    :param app_img:
    :param app_type:
    :param app_port:
    :param app_repl:
    :param app_deploy_name:
    :return:
    """
    # Configure Pod template container
    iPort = int(app_port)
    iRepl = int(app_repl)
    container = client.V1Container(
        name=app_name,
        image=app_img,
        ports=[client.V1ContainerPort(container_port=iPort)])
    # Create and configure a spec section
    template = client.V1PodTemplateSpec(
        metadata=client.V1ObjectMeta(labels={app_type: app_name}),
        spec=client.V1PodSpec(containers=[container]))
    # Create the specification of deployment
    spec = client.ExtensionsV1beta1DeploymentSpec(
        replicas=iRepl,
        template=template)
    # Instantiate the deployment object
    deployment = client.ExtensionsV1beta1Deployment(
        api_version="extensions/v1beta1",
        kind="Deployment",
        metadata=client.V1ObjectMeta(name=app_deploy_name),
        spec=spec)
    return deployment


def create_deployment(api_instance, deployment, app_namespace):
    """
    Send deployment request to k8s api using deployment object
    :param api_instance:
    :param deployment:
    :param app_namespace:
    :return:
    """
    # Create deployment
    try:
        api_response = api_instance.create_namespaced_deployment(
            body=deployment,
            namespace=app_namespace)
        print("Deployment created. status='%s'" % str(api_response.status))
    except ApiException as e:
        print("Deployment failed. status='%s'" % e)
        logging.error("Deployment failed. status='%s'" % e)
    pass


def update_deployment(api_instance, deployment, app_img, app_deploy_name, app_namespace):
    """
    update an existing deployment via k8s api edit deployment object
    :param api_instance:
    :param deployment:
    :param app_img:
    :param app_deploy_name:
    :param app_namespace:
    :return:
    """
    deployment.spec.template.spec.containers[0].image = app_img
    try:
        api_response = api_instance.patch_namespaced_deployment(
            name=app_deploy_name,
            namespace=app_namespace,
            body=deployment)
        print("Deployment updated. status='%s'" % str(api_response.status))
    except ApiException as e:
        print("Deployment update failed. status='%s'" % e)
        logging.error("Deployment update failed. status='%s'" % e)
    pass


def delete_deployment(api_instance, app_deploy_name, app_namespace):
    """
    Delete an existing deployment using k8s api request and deployment object
    :param api_instance:
    :param app_deploy_name:
    :param app_namespace:
    :return:
    """
    try:
        api_response = api_instance.delete_namespaced_deployment(
            name=app_deploy_name,
            namespace=app_namespace,
            body=client.V1DeleteOptions(
                propagation_policy='Foreground',
                grace_period_seconds=5))
        print("Deployment deleted. status='%s'" % str(api_response.status))
    except ApiException as e:
        print("Deployment deletion failed. status='%s'" % e)
        logging.error("Deployment deletion failed. status='%s'" % e)
    pass


def delete_service(api_instance, app_svcname, app_namespace):
    """
    Delete an existing deployment using k8s api request and deployment object
    :param api_instance:
    :param app_svcname:
    :param app_namespace:
    :return:
    """
    svc_body = client.V1DeleteOptions()  # V1DeleteOptions |
    try:
        api_response = api_instance.delete_namespaced_service(name=app_svcname, namespace=app_namespace, body=svc_body)
        pprint(api_response)
    except ApiException as e:
        print("Exception when calling CoreV1Api->delete_namespaced_service: %s\n" % e)
    pass


def delete_rs(api_instance, app_deploy_name, app_namespace):
    """
    Delete an existing deployment using k8s api request and deployment object
    :param api_instance:
    :param app_deploy_name:
    :param app_namespace:
    :return:
    """
    try:
        api_response = api_instance.delete_namespaced_replica_set(
            name=app_deploy_name,
            namespace=app_namespace,
            body=client.V1DeleteOptions(
                propagation_policy='Foreground',
                grace_period_seconds=5))
        print("Replicaset deleted. status='%s'" % str(api_response.status))
    except ApiException as e:
        print("Replicaset deletion failed. status='%s'" % e)
        logging.error("Replicaset deletion failed. status='%s'" % e)
    pass


def create_project_dict(app_namespace):
    """
     create a project namespace from a dictionary
    :param app_namespace:
    :return:
    """
    from openshift import client, config
    oclient_config = config.new_client_from_config()
    oapi = client.OapiApi(oclient_config)
    pretty = True  # str | If 'true', then the output is pretty printed. (optional)
    pjt_body = client.V1Project(api_version="v1",
                                kind="Project",
                                metadata={'name': app_namespace})
    try:
        api_response = oapi.create_project(pjt_body, pretty=pretty)
        pprint(api_response)
    except ApiException as e:
        print("Exception when calling ProjectOpenshiftIoV1Api->create_project: %s\n" % e)
    pass


def create_project_file(api_instance, app_yaml_file_name):
    """
     create a project from a yaml file
    :param api_instance:
    :param app_yaml_file_name:
    """
    # from openshift import client
    project_body = k8s_yaml_to_dict_helper(app_yaml_file_name)
    try:
        api_response = api_instance.create_project(body=project_body,
                                                   pretty='true')
        pprint(api_response)
    except ApiException as e:
        print("Exception when calling ProjectOpenshiftIoV1Api->create_project: %s\n" % e)
    pass


def delete_project(api_instance, app_namespace):
    """
    Deletes an existing project(Openshift) or NameSpace(K8S)
    :param api_instance:
    :param app_namespace:
    :return:
    """
    try:
        api_response = api_instance.delete_namespaced_deployment(
            name=app_namespace,
            body=client.V1DeleteOptions(
                propagation_policy='Foreground',
                grace_period_seconds=5))
        print("Project namespace deleted. status='%s'" % str(api_response.status))
    except ApiException as e:
        print("Project namespace deletion failed. status='%s'" % e)
        logging.error("Namespace deletion failed. status='%s'" % e)
    pass


def create_pod_dict(api_instance, app_name, app_img, app_namespace):
    """
    create a namespaced pod
    :param api_instance:
    :param app_name:
    :param app_img
    :param app_namespace:
    :return:
    """
    pod = client.V1Pod()
    container = client.V1Container(name=app_name)
    container.image = app_img
    container.args = ["sleep", "3600"]
    spec = client.V1PodSpec(containers=[container])
    pod.metadata = client.V1ObjectMeta(name=app_name)
    pod.spec = spec
    try:
        api_response = api_instance.create_namespaced_pod(
            namespace=app_namespace,
            body=pod)
        print("Pod created. status='%s'" % str(api_response.status))
    except ApiException as e:
        print("Pod creation failed. status='%s'" % e)
        logging.error("Pod creation failed. status='%s'" % e)
    pass


def delete_pod(api_instance, app_pod, app_namespace):
    """
    Deletes an existing namespaced pod
    :param api_instance:
    :param app_pod:
    :param app_namespace:
    :return:
    """
    try:
        api_response = api_instance.delete_namespaced_pod(
            name=app_pod,
            namespace=app_namespace,
            body=client.V1DeleteOptions(
                propagation_policy='Foreground',
                grace_period_seconds=5))
        print("Project namespace deleted. status='%s'" % str(api_response.status))
    except ApiException as e:
        print("Project namespace deletion failed. status='%s'" % e)
        logging.error("Namespace deletion failed. status='%s'" % e)
    pass


def create_node(api_instance, app_node):
    """
    create a node
    :param api_instance:
    :param app_node:
    :return:
    """
    node_body = client.V1Node()
    try:

        api_response = api_instance.create_node(
            name=app_node,
            body=node_body)
        print("Node created. status='%s'" % str(api_response.status))
    except ApiException as e:
        print("Node creation failed. status='%s'" % e)
        logging.error("Node creation failed. status='%s'" % e)
    pass


def delete_node(api_instance, app_node):
    """
    Deletes an existing node
    :param api_instance:
    :param app_node:
    :return:
    """
    try:
        api_response = api_instance.delete_node(
            name=app_node,
            body=client.V1DeleteOptions(
                propagation_policy='Foreground',
                grace_period_seconds=5))
        print("node deleted. status='%s'" % str(api_response.status))
    except ApiException as e:
        print("node deletion failed. status='%s'" % e)
        logging.error("Node deletion failed. status='%s'" % e)
    pass


def list_projects_pods_all(self):
    """
    Lists all projects and pods for all namespaces using K8S and OC API
    :return:
    """
    from openshift import client, config
    oclient_config = config.new_client_from_config()
    oapi = client.OapiApi(oclient_config)
    api = self.core_api_instance
    project_list = oapi.list_project()
    print("Projects :")
    pprint(project_list)
    print("Listing All Openshift Projects with Pods:")
    for project in project_list.items:
        project_name = project.metadata.name
        print('project: ' + project_name)
        pod_list = api.list_namespaced_pod(project_name)
        for pod in pod_list.items:
            print('    pod: ' + pod.metadata.name)
    pass


def find_project(self):
    """
    find a project
    :param self:
    :return:
    """
    from openshift import client, config
    oclient_config = config.new_client_from_config()
    oapi = client.OapiApi(oclient_config)
    project_list = oapi.list_project()
    proj_tofind = self.AppNamespace
    found_pjt = ''
    for project in project_list.items:
        project_name = project.metadata.name
        if project_name == proj_tofind:
            found_pjt = project_name
            print('project found: ' + found_pjt)
    return found_pjt


def list_projects_all():
    """
    Lists all projects for all namespaces using OC API
    :return:
    """
    from openshift import client, config
    oclient_config = config.new_client_from_config()
    oapi = client.OapiApi(oclient_config)
    print("Listing All Openshift Projects:")
    project_list = oapi.list_project()
    print('project list: ')
    pprint(project_list)
    for project in project_list.items:
        project_name = project.metadata.name
        print('project: ' + project_name)
        pprint(project.metadata)
    pass


def get_volume_list_for_deployment(self, deploy_name):
    """
    Lists all volumes for a deployment
    :param self:
    :param deploy_name:
    :return:
    """
    volList = []
    deploy_name_chk = deploy_name + '-'
    api = self.core_api_instance
    print("Listing K8S Volumes with their PVCs:")
    ret = api.list_persistent_volume()
    print('Volume list: ')
    pprint(ret)
    # if ret.metadata._continue!=None:
    for i in ret.items:
        if deploy_name_chk in i.spec.claim_ref.name:
            print("%s\t%s\t%s\t%s\t" % (i.status.phase, i.metadata.name, i.spec.claim_ref.name, i.spec.claim_ref.uid))
            volList.append((i.status.phase, i.metadata.name, i.spec.claim_ref.name, i.spec.claim_ref.uid))
    return volList


def get_volume_list(self):
    """
    List all volumes in cluster
    :return:
    """
    volList = []
    api = self.core_api_instance
    print("Listing K8S Volumes with their PVCs:")
    ret = api.list_persistent_volume()
    for i in ret.items:
        print("%s\t%s\t%s\t%s\t" % (i.status.phase, i.metadata.name, i.spec.claim_ref.name, i.spec.claim_ref.uid))
        volList.append((i.status.phase, i.metadata.name, i.spec.claim_ref.name, i.spec.claim_ref.uid))
    return volList


def get_pod_object(self, app_name):
    pod_list = get_pods_list_for_deployment(self, app_name)
    return pod_list


def get_pods_list_for_deployment(self, deploy_name):
    """
    Lists all pods with IPs for all namespaces using k8s API
    :return:
    """
    podList = []
    deploy_name_chk = deploy_name + '-'
    print("deploy name: ", deploy_name_chk)
    api = self.core_api_instance
    print("Listing K8S Pods with their IPs:")
    ret = api.list_pod_for_all_namespaces()
    for i in ret.items:
        if deploy_name_chk in i.metadata.name:
            print("found pod", i.metadata.name)
            print("%s\t%s\t%s\t" % (i.status.pod_ip, i.metadata.namespace, i.metadata.name))
            podList.append((i.status.pod_ip, i.metadata.namespace, i.metadata.name))
    return podList


def get_pods_list(self):
    """
    Lists all pods with IPs for all namespaces using k8s API
    :return:
    """
    podList = []
    api = self.core_api_instance
    print("Listing K8S Pods with their IPs:")
    ret = api.list_pod_for_all_namespaces()
    for i in ret.items:
        print("%s\t%s\t%s\t" % (i.status.pod_ip, i.metadata.namespace, i.metadata.name))
        podList.append((i.status.pod_ip, i.metadata.namespace, i.metadata.name))
    return podList


def list_pods_all(self):
    """
    Lists all pods with IPs for all namespaces using k8s API
    :return:
    """
    api = self.core_api_instance
    print("Listing K8S Pods with their IPs:")
    ret = api.list_pod_for_all_namespaces()
    print('pod list: ')
    pprint(ret)
    for i in ret.items:
        print("%s\t%s\t%s\t" % (i.status.pod_ip, i.metadata.namespace, i.metadata.name))
    pass


def find_pod(self, name):
    """
    Find Pod with a specific name
    :param self:
    :param name:
    :return:
    """
    found = False
    api = self.core_api_instance
    print("Finding K8S Pod:" + name)
    ret = api.list_pod_for_all_namespaces()
    for i in ret.items:
        print("%s\t%s\t%s" % (i.status.pod_ip, i.metadata.namespace, i.metadata.name))
        if i.metadata.name == name:
            found = True
            print('pod ' + name + 'Found!')
    return found


def get_secrets_list_for_deployment(self, deploy_name):
    """
      Lists all secrets for a particular deployment using k8s API
    :param self:
    :param deploy_name:
    :return:
    """
    secretList = []
    deploy_name_chk = deploy_name + '-'
    api = self.core_api_instance
    # print("Listing K8S Secrets with their namespace:")
    ret = api.list_secret_for_all_namespaces()
    # print('list of secrets: ')
    # pprint(ret)
    for i in ret.items:
        if (deploy_name_chk in i.metadata.name) or (i.metadata.name == 'secret-vault'):
            print("%s\t%s\t%s" % (i.metadata.namespace, i.metadata.name, i.data))
            secretList.append((i.metadata.namespace, i.metadata.name, i.data))
    return secretList


def get_secrets_list(self):
    """
    Lists all secrets for all namespaces using k8s API
    :param self:
    :return:
    """
    secretList = []
    api = self.core_api_instance
    print("Listing K8S Secrets with their namespace:")
    ret = api.list_secret_for_all_namespaces()
    print('list of secrets: ')
    pprint(ret)
    for i in ret.items:
        print("%s\t%s" % (i.metadata.namespace, i.metadata.name))
        secretList.append((i.metadata.namespace, i.metadata.name))
    return secretList


def list_secrets_all(self):
    """
    Lists all secrets for all namespaces using k8s API
    :return:
    """
    api = self.core_api_instance
    print("Listing K8S Secrets with their namespace:")
    ret = api.list_secret_for_all_namespaces()
    print('list of secrets: ')
    pprint(ret)
    for i in ret.items:
        print("%s\t%s" % (i.metadata.namespace, i.metadata.name))
    pass


def find_secret(self, name):
    """
    Lists all secrets for all namespaces using k8s API
    :return:
    """
    found = False
    api = self.core_api_instance
    ret = api.list_secret_for_all_namespaces()
    for i in ret.items:
        if i.metadata.name == name:
            found = True
            print('secret ' + name + ' Found!')
    return found


def get_svc_port_addr(endpoint_list, svc_name):
    """
    get the service object with address and port
    :param endpoint_list:
    :param svc_name:
    :return:
    """
    svc_obj = dict()
    for endpoint in endpoint_list.items:
        service_name = endpoint.metadata.name
        print('service: ' + service_name)
        for subset in endpoint.subsets:
            service_address = subset.addresses
            service_port = subset.ports
            if endpoint.metadata.name == svc_name:
                svc_obj[svc_name, 'port'] = service_port
                if service_address is None:
                    service_address = subset.not_ready_addresses
                    svc_obj[svc_name, 'address'] = service_address
    return svc_obj


def get_addr_port_list(endpoint_list, svc_name):
    """
    get a list of addr and ports for the service
    :param endpoint_list:
    :param svc_name:
    :return:
    """
    addrportList = []
    nextAddr = ''
    nextPort = ''
    print('service object: ')
    pprint(endpoint_list)
    print('service name: ' + svc_name)
    for item in endpoint_list.items:
        if item.metadata.name == svc_name:
            for subset in item.subsets:
                service_port = subset.ports
                service_address = subset.addresses
                if service_address is None:
                    service_address = subset.not_ready_addresses

                for portObj in service_port:
                    nextPort = str(portObj.port)

                for addrObj in service_address:
                    nextAddr = addrObj.ip
                    addrportList.append((nextPort, nextAddr))

    return addrportList


def get_svc_endpoints(self, svc_namespace, svc_name):
    """
     get the service endpoints in a specific namespace
    :param self:
    :param svc_namespace:
    :param svc_name:
    :return:
    """
    api_instance = self.core_api_instance
    pretty = True
    print("Service Namespace is: " + svc_namespace)
    print("Service Name is : " + svc_name)
    try:
        endpoint_list = api_instance.list_namespaced_endpoints(svc_namespace, pretty=pretty)
        pprint(endpoint_list)
        return endpoint_list
    except ApiException as e:
        print("Exception when calling CoreV1Api->list_namespaced_endpoints: %s\n" % e)
    pass
