## A module to work with AMIs for the purpose of debugging and updating.
import boto3
import sys
import time
import os
import re
import datetime
import subprocess
import json
import pathlib
import docker

if "pytest" in sys.modules:
    mode = "test"
else:
    mode = "std"

cfn_client = boto3.client("cloudformation")


if mode == "std":
    default_tag = "latest"
    default_repo = "continuumio/anaconda3"
    default_neurocaas_repo = "neurocaas/contrib"
    default_neurocaas_repo_tag = "base"
    default_command = "/bin/bash"
    repo_path = os.path.realpath(os.path.join(os.path.dirname(os.path.realpath(__file__)),"../../"))
elif mode == "test":
    default_tag = "latest"
    default_repo = "bash"
    default_neurocaas_repo = "test_local_build"
    default_neurocaas_repo_tag = "latest"
    default_command = "ls"
    repo_path = os.path.realpath(os.path.join(os.path.dirname(os.path.realpath(__file__)),"../../","tests","test_mats"))

default_image = f"{default_neurocaas_repo}:{default_neurocaas_repo_tag}"
default_root_image = f"{default_repo}:{default_tag}"

## 11/30/20
class NeuroCAASImage(object):
    """NeuroCAAS image management. Builds a docker image from the dockerfile, if needed, or attaches to a known one.  

    """
    def __init__(self,image_tag=None,container_name="neurocaasdevcontainer"):
        """Initialize the NeuroCAASImage object.
        
        :param image_tag: (optional) The image tag identifying the image we want to load. Should be given in the form repository:tag. If not given, will default to using/building the default neurocaas image. 
        """
        self.client = docker.from_env()
        self.container_name = container_name # check this is all lowercase.
        if image_tag is None:
            self.image = self.get_default_image()
            self.image_tag = default_image   
        else: 
            ## See if the image requested is available:
            try:
                self.find_image(image_tag)
                self.image = self.client.images.get(image_tag)
                self.image_tag = image_tag
            ## Handle the case where no image exists:
            except AssertionError as e:
                print(f"Error while loading requested image: {e}. Loading in default image.")
                self.image = self.get_default_image()
        ## Sequence of all containers associated with this image.
        self.container_history = {} 

    def find_image(self,image_tag):
        """Looks to see if the image requested is locally available. Raises an exception if not.

        :param image_tag: a tag given to the image we are discussing. 

        """
        all_images = self.client.images.list()
        all_tags = [i.tags for i in all_images]
        assert any([image_tag in tags for tags in all_tags]),"Image tag not found. Please format as repository:tag. To see all images available, run `docker images` from the command line."

    def build_default_image(self):
        """Builds the default image from Dockerfile.

        """
        try:
            self.find_image(f"{default_repo}:{default_tag}")
        except AssertionError:
            print(f"Pulling {default_tag} version of repository {default_repo}")
            self.client.images.pull(default_repo,tag = default_tag)

        image,logs = self.client.images.build(path = repo_path,quiet = False,tag = default_neurocaas_repo)
        return image,logs

    def get_default_image(self):
        """Gets the default image. If it can't be found, pulls the anaconda3 image and builds from Dockerfile. 

        """
        ## First try to find the default image.
        try:
            self.find_image(default_image)
            return self.client.images.get(default_image)
        except AssertionError:
            print("Default image not available. Pulling from Docker Hub.")
            try:
                print(f"Pulling {default_neurocaas_repo_tag} version of repository {default_neurocaas_repo}. Please wait...")
                image = self.client.images.pull(default_neurocaas_repo,tag = default_neurocaas_repo_tag)
                if type(image) is list:
                    print("Got many tags, providing first image")
                    image = image[0]
            except docker.errors.APIError: 
                print(f"Pull failed. Building default image from Anaconda base.")
                image,logs = self.build_default_image()
            except Exception as e:
                print(f"unhandled exception: {e}")
        return image 

    def setup_container(self,image_tag = None,container_name = None):
        """Probably the most important method in this class. Runs a container off of the image that you created, or another image of your choice. If you include a new image tag, all subsequent commands (until you run this command again) will refer to the corresponding image.  
        :param image_tag: (optional) The name of an image, with the tag parameter specified. If given, will launch a container from this image, and set this object to interface with that image tag from now on (start containers from that image, test that image, etc.) 
        :param container_name: (optional) If given, will launch a container with that name attached. Note this must be lowercase. If not given, will launch with the default name at self.container_name.
        """
        if container_name is None:
            ## Check that it's all lowercase
            container_name = self.container_name
        if image_tag is not None:
            ## Will return assertion error if image is not found.
            self.find_image(image_tag)
            self.image = self.client.images.get(image_tag)
            self.image_tag = image_tag
        container = self.client.containers.run(self.image_tag,default_command,name = container_name ,stdin_open = True,tty = True,detach = True)

        print(f"Container is running as {container_name}. You can connect to it by running: \n\n  `docker exec -it {container_name} /bin/bash` \n\n from the command line. The container can now be accessed at attribute current_container.")
        ## Set 
        self.container_name = container_name 
        self.current_container = container
        self.container_history[container.id] = container

    def test_container(self,command,container_name = None):
        """Test the container with a command. If no container name is given, the container with name at self.container_name will be used.

        :param command: (str) a string representing the command you would like to be executed by the bash shell inside the container. Will be passed to /bin/bash inside the container as `docker exec [container_name] /bin/bash -c '[command]'. We recommend passing this string with single quotes on the outside, and double quotes for shell arguments: ex. `NeuroCAASImage.test_container(command = \'run.sh \"parameter1\"\'`
        :param container_name: (optional) The name of the container where we should run the given command.
        """
        ## First get the container:
        if container_name is None:
            container_name = self.container_name
        container = self.client.containers.get(container_name)
        output = container.exec_run(f"/bin/bash -c '{command}'",detach = False,stream=True)
        try:
            print("[Test Execution Starting: Output to command line below]")
            while True:
                print(next(output.output).decode("utf-8"))
        except StopIteration:
            print("[Test Execution Done]")

    def save_container_to_image(self,tag,force = False):
        """Once you have made appropriate changes and tested, you will want to save your running container to a new image. This image will be specified as a tag; i.e., your image's name will be neurocaas/contrib:[tag]. 
        :param tag: The tag that will be used to identify this image. We recommend providing your tag as the name of your analysis repo + a git commit, like neurocaas/contrib:mockanalysis.356d78a, where 356d78a is the output of running `git rev-parse --short HEAD` from your git repo. If you provide a tag that is already in use, you will have to provide a "force=True" argument.   
        :param force: (optional) Whether or not to overwrite an image with this name already. Default is force = False
        """
        ## First create the requested tag:
        image_tag = f"{default_neurocaas_repo}:{tag}"
        ## See if this exists:
        if force is False:
            try:
                self.find_image(image_tag)
                print("An image with name {image_tag} already exists. To overwrite it, call this method with parameter force = True")
                return
            except AssertionError: 
                print("This tag is available, proceeding with commit.")
        else:
            pass
        container = self.current_container
        try:
            container.commit(repository=default_neurocaas_repo,tag=tag)
            print(f"Success! Container saved as image {image_tag}")
        except docker.errors.APIError:
            print(f"Unable to commit container. You can try manually from the command line by calling `docker commit [container name] {default_neurocaas_repo}:{tag}`")



## 11/23/20
class NeuroCAASAutoScript(object):
    """Developer tool to automate creation and testing of an analysis-specific bash script.   

    """
    def __init__(self,scriptjson,templatepath):
        """
        :param scriptjson: a json script that specifies all of the parameters necessary to set up a local analysis environment. Tells us to start a python environment check if we need to communicate to the gpu, as well as the locations to which we should load local data and write output. 
        """
        ## Check for all necessary arguments in the config file:
        with open(scriptjson,"r") as f:
            scriptdict = json.load(f)
        args_req = {"script_name":str,"in":dict,"out":dict,"user_root_dir":str}
        for ar in args_req: 
            assert ar in scriptdict.keys()
            assert type(scriptdict[ar]) == args_req[ar], "scriptdict is misformatted: type for '{}' is {}, should be {}".format(ar,type(ar),args_req[ar])
        self.scriptdict = scriptdict

        ## Load in data from template script:
        with open(templatepath,"r") as f:
            scriptlines = (f.readlines())
        assert scriptlines[0].startswith("#!/bin/bash"), "We must initialize from and build a bash script."
        self.scriptlines = scriptlines

        ## Now we start doing setup: 
        if "dlami" in scriptdict.keys() is scriptdict["dlami"] is "true":
            self.add_dlami()

        if "env_name" in scriptdict.keys() and scriptdict["env_name"] is not None:
            if "conda_dir" in scriptdict.keys() and scriptdict["conda_dir"] is not None:
                path = scriptdict["conda_dir"]
            else:
                path = None
            self.add_conda_env(path = path)

    def add_dlami(self):
        """Sources the dlami bash script to correctly configure the ec2 os environment with GPU. 

        """
        self.scriptlines.append("\n")
        self.scriptlines.append("## AUTO ADDED DLAMI SETUP \n")
        self.scriptlines.append("source .dlamirc")

    def append_conda_path_command(self,path = None):
        """Generates the material we want to append to the python path to find the anaconda environment correctly. Will assume that anaconda(3) is installed in the user's home directory. An alternative path to anaconda3/bin can be supplied if this is not the case.   
        :param path: (optional) if given, will check that the anaconda bin exists at that location, instead of being installed in the user's root directory
        :return: the bash command we will use to appropriately format the anaconda path. 
        """
        if path is None:
            path = os.path.join(self.scriptdict["user_root_dir"],"anaconda3/bin")
            
        ## First check that this path exists and is appropriately formatted.
        assert path.endswith("/bin"), "Path must end with *conda{}/bin."
        assert os.path.isdir(path),f"The path {path} does not exist. Please add/revise a manually added path to the anaconda bin."
        
        command = "export PATH=\"{}:$PATH\"".format(path)
        return command

    def check_conda_env(self,env_name):
        """Checks if a conda env exists on this machine, and returns a boolean exists/not exists.

        :param env_name: environment name. 
        :return: boolean, if this environment exists or not. 
        """

        all_env_str = subprocess.check_output('conda env list',shell = True).decode("utf-8")
        all_env_info = all_env_str.split("\n")[2:]
        condition = any([env_info.startswith(env_name+" ") for env_info in all_env_info])

        return condition 


    def add_conda_env(self,check = True,path = None):
        """Adds commands to enter a conda virtual environment to template script. If check, will check that this virtual environment exists before adding.  

        :param check: boolean asking if we should check that the environment exists first or not.
        :param path: (optional) if provided, looks here for the conda installation. Otherwise will defaults to $user_root_dir/conda_dir(anaconda3 if not provided).

        """
        env_name = self.scriptdict["env_name"]
        if check:
            assert self.check_conda_env(env_name),"conda environment must exist"

        setupcommand = self.append_conda_path_command(path)+" \n"
        declarecommand = f"conda activate {env_name}"+" \n"

        #Now add the suggested lines to the script:  
        self.scriptlines.append("\n")
        self.scriptlines.append("## AUTO ADDED ENV SETUP \n")
        self.scriptlines.append(setupcommand)
        self.scriptlines.append(declarecommand)



    def write_new_script(self,filename):
        """Writes the current contents of scriptlines to file. 

        :param filename: name of file to write to. 
        
        """
        with open(filename,"w") as f:
            f.writelines(self.scriptlines)

    def check_dirs(self):
        """Add lines to the bash script to check if the local locations for input/output specified in the script dictionary exist. If they do not, creates them with the appropriate permissions. 

        """
        local_locs = [item["local_location"] for item in self.scriptdict["in"].values()] + [item["local_location"] for item in self.scriptdict["out"].values()]
        locs_unique = set(local_locs)
        create_commands = ["mkdir -p \"{}\"".format(os.path.join(loc,"")) for loc in locs_unique]
        #loc_string = " ".join(["\"{loc}\"".format(loc = os.path.join(loc,"")) for loc in locs_unique])
        self.scriptlines.append("\n")
        self.scriptlines.append("## AUTO ADDED DIRECTORY CREATION \n")
        for com in create_commands:
            self.scriptlines.append(com)

    def get_inputs(self):
        """Write the  

        """

## 8/20/20 Sketch out a new class that will form the basis of the new python package.  
class NeuroCAASDeveloperInterface(object):
    """New developer interface that will form the basis for a python package. 

    """
    def __init__(self,pipelinename):
        """
        ## 1. Checks that pipeline name is not already taken on account. Notifies if the name already exists (we can check this on pull request). 
        ## 2. Creates a tag value for the developer's IAM credentials that indicates they are working with pipeline of given name. Ensures that you can only work with one pipeline at a time, and that they are monitored. This tag value should be encrypted, so that developers cannot provide the tag manually and launch as many instances as they would like.  
        """
        try:
            response = cfn_client.describe_stacks(pipelinename)
        #TODO
        except:
            pass

    def initialize_blueprint(instance_type,ami,region):
        """
        Initializes a blueprint with the basic info needed to get an instance up and running.    
        ## Creates a special directory where pipeline specific information will be stored.  
        """
        pass

    def load_blueprint(path):
        """
        If continuing development on a pipeline that already exists, you can load the information from it directly. 
        """
        pass

    def launch_development_instance():
        """
        Launch a development instance from the blueprint you are building. 
        """
        pass

