#! /usr/bin/python3

#-------------------------------
#   Author: b15benko/Mirakelsvampen
#   Course: IT508G
#   Date:   03/02/2018
#   To:     University of Skövde
#   Email:  b15benko@student.his.se
#-------------------------------

import pyVmomi
import sys
import ssl
from pyVim.connect import SmartConnect, Disconnect
from pyVmomi import vim, vmodl

def create_switch(*args):
    """
        Create a virtual switch for a host.
        The arguments are given in order from line 170-178
    """
    for node in args[0].host: # iterate through all hosts in cluster
        network_system = node.configManager.networkSystem

        sw_spec = vim.host.VirtualSwitch.Specification() # create a template-ish object
        sw_spec.numPorts = int(args[2])
        if len(args) == 5: # See if the optional parameter is given (Physical NIC)
            sw_spec.bridge = vim.host.VirtualSwitch.BondBridge(nicDevice=[args[4]])
        sw_spec.mtu = int(args[3])
        network_system.AddVirtualSwitch(vswitchName=args[1], spec=sw_spec)
    return True

def create_port_group(*args):
    """
        Create a port group and a VLAN, then attach
        a vSwitch to it.

        The arguments are indexed meaning that
        they are given in a specific order.

    """
    for node in args[0].host: # iterate through all hosts in cluster
        network_system = node.configManager.networkSystem

        port_group_spec = vim.host.PortGroup.Specification() # Create a specification tree (Looks like JSON)
        port_group_spec.name = args[1] # assign a name to the specs
        port_group_spec.vswitchName = args[2] # assign a vSwitch to portgroup
        port_group_spec.vlanId = args[3] # assign a VID

        security_policy = vim.host.NetworkPolicy.SecurityPolicy() # set standard security policies
        security_policy.allowPromiscuous = True 
        security_policy.forgedTransmits = True
        security_policy.macChanges = False
        port_group_spec.policy = vim.host.NetworkPolicy(security=security_policy)
        
        network_system.AddPortGroup(portgrp=port_group_spec) # Create the portgroup with the new specifications
    return True

def connect():
    """
        Create a connection to a VMware host.
        1. First attempt with a valid cert.
        2. If no valid cert, then try without cert
        and notify this to the user.
        3. If this does not work then an exception is raised
        and notify the user.
    """
    try:
        try: # Try to connect with default SSL options
            connection = SmartConnect(host="10.207.3.10", user="administrator@b15benko.nsa.his.se", pwd='Syp9393!!') 
            return (1, connection)
        except ssl.SSLError: # By pass SSL errors if any are given
            cert = ssl.SSLContext(ssl.PROTOCOL_TLSv1)
            cert.verify_mode = ssl.CERT_NONE # bypass SSL errors, whoops...
            connection = SmartConnect(host="10.207.3.10", user="administrator@b15benko.nsa.his.se", pwd='Syp9393!!', sslContext=cert) 
            return (2, connection)
    except Exception as err: 
        return (3, err)

def main():
    """
        main block, handles all output,
        error handling, and function
        callings.

        This whole block can be removed if
        this script is used as a module
    """
    print('Attempting to connect...')
    c = connect() # returns a tuple: (1, connection) or (2, error_msg) or (3, connection)
    if c[0] == 1:
        connection = c[1] # The second index contains the connection information
        print('Logged in anyways, but check your certificate!')
    elif c[0] == 2:
        connection = c[1] # The second index contains the connection information
        print('WARNING: Invalid certificate.\nSuccess!')
    elif c[0] == 3:
        print('Something went wrong: {}'.formt(c[1])) # the second index contains the raised exception
        sys.exit()

    try:
        if len(sys.argv) < 7: # perform some error checks before moving on the other selection blocks
            raise IndexError

        cluster_name = sys.argv[1]
        switch_name = sys.argv[2]

        MTU = sys.argv[3]
        if MTU.isdigit() == False:
            raise NameError('Argument error: MTU can only contain numerical symbols(1000-9000).') # just use NameError for no obvious reasons (besides the name)
            sys.exit
        elif MTU.isdigit() == True and (int(MTU) < 1500 or int(MTU) > 9000):
            raise NameError('Argument error: MTU cannot be lower than 1500 or higher than 9000.')
        elif MTU.isdigit() == True and (int(MTU) > 1500 and int(MTU) < 9000):
            MTU = int(MTU) # convert to integer, the API does not like strings when numbers are necessary

        num_port = sys.argv[4]
        if num_port.isdigit() == False:
            raise NameError('Argument error: port number can only contain numbers(1-1024).')
        elif num_port.isdigit() == True and (int(num_port) < 1 or int(num_port) > 1024):
            raise NameError('The number of ports may not exceed 1024 or be lower than 1.')
        else:
            num_port = int(num_port) # convert to integer, the API does not like strings when numbers are necessary

        port_group_name = sys.argv[5]

        VID = sys.argv[6]
        if VID.isdigit() == False:
            raise NameError('Argument error: VID can only contain numbers.')
            sys.exit
        elif VID.isdigit() == True and (int(VID) < 0 or int(VID) > 4095):
            print('VID cannot be lower than 0 or exceed 4095.')
        elif VID.isdigit() == True and (int(VID) > 0 and int(VID) < 4095):
            VID = int(VID) # convert to integer, the API does not like strings when numbers are necessary

        print('Attempting to create vSwitch with following settings:')
        print(' Cluster'.ljust(20, '.') + '{}'.format(cluster_name))
        print(' Name'.ljust(20, '.') + '{}'.format(switch_name))
        print(' MTU'.ljust(20, '.') + '{}'.format(MTU))
        print(' Number of ports'.ljust(20, '.') + '{}'.format(num_port))
        print(' Port group'.ljust(20, '.') + '{}'.format(port_group_name))
        print(' VLAN'.ljust(20, '.') + '{}'.format(VID))
        if len(sys.argv) == 9:
            nic_name = sys.argv[8]
            print(' Physical NIC'.ljust(20, '.') + '{}'.format(nic_name))

        inventory = connection.RetrieveContent() # Retrieve the start of the API heirarchy
        dc = inventory.rootFolder.childEntity[0]
        cluster = dc.hostFolder.childEntity[0]
        
        if 'nic_name' in locals(): # see if optional argument is given, if not then do not pass it to the function
            if create_switch(cluster, switch_name, num_port, MTU, nic_name) == True:
                print('{} created with {} ports and attached to {}...'.format(  
                                                                                switch_name, 
                                                                                num_port, 
                                                                                nic_name
                                                                            ))
        else:
            if create_switch(cluster, switch_name, num_port, MTU) == True:
                print('{} created with {} ports...'.format(
                                                            switch_name, 
                                                            num_port
                                                        ))

        if create_port_group(cluster, port_group_name, switch_name, VID) == True: # Create portgroup and assign new vSwitch to it
            print('{} added to the portgroup {}...'.format(
                                                            switch_name, 
                                                            port_group_name
                                                        ))

    except IndexError as err:
        print('Missing parameter(s) - Usage:\n>  ./vSwitch.py <Target cluster name> <Switch_name> <MTU(1000-9000)> <Number_of_ports(1-1024)> <VLAN_name> <VLAN_ID(1-4095)> <OPTIONAL: Physical_NIC_name>')
        sys.exit()
    except NameError as err:
        print(err)
        sys.exit()
    
    print('Done.')
    Disconnect(connection) # Disconnect first before existing program, to ensure the cluster terminates the connection as well
    sys.exit() # Exit the script

if __name__ == "__main__": 
    main()

