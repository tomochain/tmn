import sys
import docker as dockerpy
from tmn import compose
from tmn import display

_client = None


def apierror(function):
    """
    Decorator to catch `docker.errors.APIerror` Exception

    :param function: function to decorate
    :type function: function
    :returns: decorated function
    :rtype: function
    """
    def wrapper(*args, **kwargs):
        try:
            function(*args, **kwargs)
        except dockerpy.errors.APIError:
            display.error_docker_api()
            sys.exit()
    return wrapper


def connect(url=None):
    """
    Create the docker client. Try to ping the docker server to establish if
    the connexion in successful

    :param url: url to the docker deamon
    :type url: str
    """
    global _client
    if not url:
        _client = dockerpy.from_env()
    else:
        _client = dockerpy.DockerClient(base_url=url)
    return _ping()


def _ping():
    """
    Try to ping the Docker daemon. Check if accessible.

    :returns: is Docker running
    :rtype: bool
    """
    try:
        return _client.ping()
    except Exception:
        return False


def _create_volumes():
    """
    Try to get the volumes defined in `VOLUMES`. If it fails, create them.
    """
    for volume in compose.volumes:
        display.step_create_masternode_volume(volume)
        try:
            _client.volumes.get(volume)
            display.step_close_exists()
        except dockerpy.errors.NotFound:
            _client.volumes.create(volume)
            display.step_close_created()
    display.newline()


def _create_networks():
    """
    Try to get the networks defined in `NETWORKS`. If it fails, create them.
    """
    for network in compose.networks:
        display.step_create_masternode_network(network)
        try:
            _client.networks.get(network)
            display.step_close_exists()
        except dockerpy.errors.NotFound:
            _client.networks.create(network)
            display.step_close_created()
    display.newline()


def _get_existing_containers():
    """
    Get from docker the containers defined in `CONTAINERS`.

    :returns: The existing `docker.Container`
    :rtype: list
    """
    containers = {}
    for key, value in compose.containers.items():
        try:
            container = _client.containers.get(value['name'])
            containers[container.name] = container
        except dockerpy.errors.NotFound:
            pass
    return containers


def _create_containers():
    """
    Try to get the containers defined in `CONTAINERS`.
    If it fails, create them.

    :returns: The created or existing `docker.Container`
    :rtype: list
    """
    containers = {}
    for key, value in compose.containers.items():
        display.step_create_masternode_container(value['name'])
        try:
            container = _client.containers.get(value['name'])
            display.step_close_exists()
        except dockerpy.errors.NotFound:
            # temporary, see https://github.com/docker/docker-py/issues/2101
            _client.images.pull(value['image'])
            container = _client.containers.create(**value)
            display.step_close_created()
        containers[container.name] = container
    return containers


def _start_containers(containers):
    """
    Verify the container status. If it's not restarting or running,
    start them.

    :param containers: dict of name:`docker.Container`
    :type containers: dict
    """
    for name, container in containers.items():
        display.step_start_masternode_container(container.name)
        container.reload()
        # filtered status are:
        # created|restarting|running|removing|paused|exited|dead
        # might have to add all the status
        if container.status in ['restarting', 'running']:
            pass
        elif container.status in ['paused']:
            container.unpause()
        elif container.status in ['created', 'exited', 'dead']:
            container.start()
        container.reload()
        display.step_close_status(container.status)


def _stop_containers(containers):
    """
    Stop the given dict of `docker.Container`

    :param containers: dict of name:`docker.Container`
    :type containers: dict
    """
    for name, container in containers.items():
        display.step_stop_masternode_container(container.name)
        container.reload()
        # filtered status are:
        # created|restarting|running|removing|paused|exited|dead
        # might have to add all the status
        if container.status in ['restarting', 'running', 'paused']:
            container.stop()
        elif container.status in ['created', 'exited', 'dead']:
            pass
        container.reload()
        display.step_close_status(container.status)


def _status_containers(containers):
    """
    Display the status of `CONTAINERS` w/ the passed list of `docker.Container`

    :param containers: dict of `docker.Container`
    :type containers: dict
    """
    names = [
        compose.containers[container]['name']
        for container in list(compose.containers)
    ]
    for name in names:
        display_kwargs = {}
        display_kwargs.update({'name': name})
        try:
            containers[name].reload()
            if containers[name].status in ['running']:
                display_kwargs.update({'status_color': 'green'})
            display_kwargs.update({'status': containers[name].status})
            display_kwargs.update({'id': containers[name].short_id})
        except KeyError:
            display_kwargs.update({'name': name})
            display_kwargs.update({'name': name})
        display.status(**display_kwargs)


@apierror
def start():
    """
    Start a masternode. Includes:
    - creating volumes
    - creating networks
    - creating containers
    - starting containers
    """
    compose.process()
    display.subtitle_create_volumes()
    _create_volumes()
    display.subtitle_create_networks()
    _create_networks()
    display.subtitle_create_containers()
    containers = _create_containers()
    display.newline()
    _start_containers(containers)


@apierror
def stop():
    """
    Stop a masternode. Includes:
    - getting the list of containers
    - stoping them
    """
    compose.process()
    containers = _get_existing_containers()
    _stop_containers(containers)


@apierror
def status():
    """
    Retrieve masternode status. Includes:
    - getting the list of containers
    - displaying their status
    """
    compose.process()
    containers = _get_existing_containers()
    _status_containers(containers)
