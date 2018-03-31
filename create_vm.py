#! /usr/bin/python3

#-------------------------------
#   Author: b15benko/Mirakelsvampen
#   Course: IT508G
#   Date:   22/02/2018
#   To:     University of Skövde
#   Email:  b15benko@student.his.se
#-------------------------------

# Usage: python3 create_vm.py <VM name> <port group> <CPU's> <Memory allocation GB> <Disk Space GB>

import pyVmomi
import sys
import ssl
from pyVim.connect import SmartConnect, Disconnect
from pyVmomi import vim, vmodl
from time import sleep

def select_network(datacenter, net_name):
    """
        Convert the user network name input from
        string to API method. this is important
        for the NIC creation when a VM is created.
    """
    for i in datacenter.network:
        if i.name == net_name:
            return i

def vm_name_check(vm_folder, vm_name):
    """
        Check if the vm_name given by the
        user already exists.
    """
    vms = [vm.name for vm in vm_folder.childEntity]
    if vm_name in vms:
        return False
    else:
        return True

def memory_check(datacenter, RAM):
    """
        Check if the RAM given by
        the user is less than the
        maximum available memory
        in the cluster.

        According to API: effectiveMemory = Effective memory resources (in MB) available to run virtual machines. 
        This is the aggregated effective resource level from all running hosts. 
        Hosts that are in maintenance mode or are unresponsive are not counted. 
        Resources used by the VMware Service Console are not included in the aggregate. 
        This value represents the amount of resources available for the root resource pool for running virtual machines.
    """
    available_mem = datacenter.hostFolder.childEntity[0].summary.effectiveMemory
    if RAM < available_mem:
        return True # enough free memory
    else:
        return False # not enough free memory

def cpu_check(datacenter, CPU):
    """
        Check if the CPU given by
        the user is less than the
        maximum CPU cores
        in the cluster.

        According to API: numCpuCores = Number of physical CPU cores. Physical CPU cores are the processors contained by a CPU package.
    """
    available_cpu = datacenter.hostFolder.childEntity[0].summary.numCpuCores
    if CPU < available_cpu:
        return True # enough free memory
    else:
        return False # not enough free memory

def datastore_space_check(datacenter, disk):
    nfs_store = [datastore for datastore in datacenter.hostFolder.childEntity[0].datastore if datastore.name == 'NFS_share'][0]
    free_space = nfs_store.summary.freeSpace // 1024  # this converted to KB since it comes as bytes from the API
    if disk < free_space:
        return True
    else:
        return False

def convert_gb_to_mb(RAM):
    """
        used for creating a disk, the API
        only takes Megabytes
    """
    return 1024 * int(RAM)

def convert_gb_to_kb(disk):
    """
        used for creating a disk, the API
        only takes bytes or Kilo-bytes
    """
    return int(disk) * (1024 * 1024)

def convert_kb_to_gb(disk):
    """
        used to preserve the original input
    """
    return int(disk) // (1024 * 1024)

def mb_to_gb(RAM):
    """
        used to preserve the original input
    """
    return int(RAM) // 1024 

def connect():
    """
        Create a connection to a VMware host.
        1. First attempt with a valid cert.
        2. If no valid cert, then try without cert
        and notify this to the user.
        3. If this does not work then an exception is raised
        and notify the user.
    """
    cert = ssl.SSLContext(ssl.PROTOCOL_TLSv1)
    cert.verify_mode = ssl.CERT_NONE # ignore SSL

    try:
        try:
            connection = SmartConnect(host="10.207.3.10", user="administrator@b15benko.nsa.his.se", pwd='Syp9393!!') 
            return (1, connection)
        except ssl.SSLError:
            connection = SmartConnect(host="10.207.3.10", user="administrator@b15benko.nsa.his.se", pwd='Syp9393!!', sslContext=cert) 
            return (2, connection)
    except Exception as err: 
        return (3, err)

def create_vm(vm_folder, resource_pool, datastore, net_name, vm_name, CPU, RAM, disk, provision):
    """
        Create a VM with following configurations: CPU, memory, disk
        RAM and attached network/switch
    """
    new_datastore = '[' + datastore.name + '] ' + vm_name # This creates a new directory with the same naming scheme as the new VM
    vm_config = vim.vm.ConfigSpec()
    """ 
        Create a custom nic specification...
        behold!... this is just a cluster of methods
        going back and forth...
        Exactly how this looks behind the scenes is explained
        in the report
    """
    device_config = []
    # Create NIC
    nic_type = vim.vm.device.VirtualE1000()
    nic_edit = vim.vm.device.VirtualDeviceSpec() # Create a "template" for a new NIC
    nic_edit.operation = vim.vm.device.VirtualDeviceSpec.Operation.add # tell the API that we want to create a new device
    nic_edit.device = nic_type # create a device specikation with the nic_edit name
    nic_edit.device.deviceInfo = vim.Description() # Initialize methods to set info for the NIC
    nic_edit.device.backing = vim.vm.device.VirtualEthernetCard.NetworkBackingInfo() # Add backing information to the device specification
    nic_edit.device.backing.network = net_name # Associate an existing network with the device description
    nic_edit.device.backing.deviceName = net_name.name # set the device name to the physical or logical network the nic is connected to.
    device_config.append(nic_edit)


    # addd iscsi controller to machine
    scsi_type = vim.vm.device.VirtualLsiLogicController()
    scsi_ctl = vim.vm.device.VirtualDeviceSpec()
    scsi_ctl.operation = vim.vm.device.VirtualDeviceSpec.Operation.add
    scsi_ctl.device = scsi_type
    scsi_ctl.device.deviceInfo = vim.Description()
    scsi_ctl.device.slotInfo = vim.vm.device.VirtualDevice.PciBusSlotInfo()
    scsi_ctl.device.slotInfo.pciSlotNumber = 16
    scsi_ctl.device.key = 22 # random number
    scsi_ctl.device.sharedBus = vim.vm.device.VirtualSCSIController.sharedBus = 'noSharing'
    scsi_ctl.device.busNumber = 0
    scsi_ctl.device.device = 0
    scsi_ctl.device.scsiCtlrUnitNumber = 7
    device_config.append(scsi_ctl)

    vm_config.numCPUs = CPU
    vm_config.name = vm_name
    vm_config.memoryMB = RAM
    vm_config.guestId = 'ubuntu64Guest'
    vm_config.deviceChange = device_config # Set custom hardware specications from the newly created NIC and vHDD

    vm_files = vim.vm.FileInfo()
    vm_files.vmPathName = new_datastore
    vm_config.files = vm_files
    
    print('\nCreating VM without disk...')
    vm_folder.CreateVM_Task(config=vm_config, pool=resource_pool)
    add_disk_to_vm(vm_folder, vm_name, disk, provision, datastore)
    return True

def add_disk_to_vm(vm_folder, vm_name, disk, provision, datastore):
    device_config = []
    sleep(5)
    print('\nAdding disk now...')
    # Create virtualdisk
    spec = vim.vm.ConfigSpec()
    vm = [dev for dev in vm_folder.childEntity if dev.name==vm_name][0]
    for dev in vm.config.hardware.device:
        if dev.unitNumber:
            unit_number = int(dev.unitNumber) + 1
            # unit_number 7 reserved for scsi controller
            if unit_number == 7:
                unit_number += 1
        if isinstance(dev, vim.vm.device.VirtualLsiLogicController):
            controller = dev

    # add disk here
    dev_changes = []
    new_disk_kb = int(disk)
    disk_spec = vim.vm.device.VirtualDeviceSpec()
    disk_spec.fileOperation = "create"
    disk_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.add
    disk_spec.device = vim.vm.device.VirtualDisk()
    disk_spec.device.backing = \
        vim.vm.device.VirtualDisk.FlatVer2BackingInfo()
    if provision == 'thin':
        disk_spec.device.backing.thinProvisioned = True
    disk_spec.device.backing.diskMode = 'persistent'
    disk_spec.device.unitNumber = unit_number
    disk_spec.device.capacityInKB = new_disk_kb
    disk_spec.device.controllerKey = controller.key
    dev_changes.append(disk_spec)
    spec.deviceChange = dev_changes
    vm.ReconfigVM_Task(spec=spec)

def main():
    print('Attempting to connect...')
    c = connect() # returns a tuple: (1, connection) or (2, error_msg) or (3, connection)
    if c[0] == 1:
        connection = c[1] # The second index contains the connection information
        print('Success')
    elif c[0] == 2:
        connection = c[1] # The second index contains the connection information
        print('WARNING: Invalid certificate.\nSuccessfully connected anyways because magic.')
    elif c[0] == 3:
        print('Something went wrong: {}'.format(c[1])) # the second index contains the raised exception
        sys.exit()

    inventory = connection.RetrieveContent()
    datacenter = inventory.rootFolder.childEntity[0] # first datacenter (the only one)
    vm_folder = datacenter.vmFolder # This folder is used to place the VM in
    resource_pool = datacenter.hostFolder.childEntity[0].resourcePool # the resource pool of the first and only cluster
    datastore = datacenter.hostFolder.childEntity[0].datastore[0] # NFS_share (indexing can be different when more datastores are added)

    try:
        if len(sys.argv) < 6:
            raise IndexError

        vm_name = sys.argv[1]
        if vm_name_check(vm_folder, vm_name) == False:
            raise NameError('\nVM with the name "{}" already exists.'.format(vm_name))

        port_group = sys.argv[2] # create a checker that looks for exisitng port groups

        CPU = sys.argv[3]
        if CPU.isdigit() == False:
            raise NameError('\nCPU value must be numerical')
            sys.exit()
        elif CPU.isdigit() == True:
            CPU = int(CPU)
            if cpu_check(datacenter, CPU) == False:
                raise NameError('\nNo sufficient CPU cores in cluster...')
                    
        RAM = sys.argv[4] # in megabytes. Must implement a GB to MB converter!
        if RAM.isdigit() == True:
            RAM = convert_gb_to_mb(RAM)
            if memory_check(datacenter, RAM) == False:
                raise NameError('\nNo sufficient memory in cluster...')
        elif RAM.isdigit() == False:
            raise NameError('\nRAM size must be numerical')
            sys.exit()

        disk = sys.argv[5] # must be numberical
        if disk.isdigit() == False:
            raise NameError('\nDisk size must be numerical')
            sys.exit()
        elif disk.isdigit() == True:
            disk = convert_gb_to_kb(disk)
            if datastore_space_check(datacenter, disk) == False:
                raise NameError('\nNo sufficient space in datastore...')
        
        provision = sys.argv[6]
        if provision == 'thin' or provision == 'thick':
            pass
        else:
            raise NameError('\nCan only be the "thin" or "thick". It determines if thin provisioning should be used or not')

    except IndexError as err:
        print('\nMissing paramters - Usage:\n python3 create_vm.py <VM name> <port group> <CPU\s> <Memory allocation: GB> <Disk Space: GB> <Thin provisioning: true/false>')
        sys.exit()
    except NameError as err:
        print(err)
        sys.exit()

    print('\nAttempting to create Virtual machine with following settings:')
    #print(' Cluster'.ljust(20, '.') + '{}'.format(cluster_name))
    print(' Name'.ljust(20, '.') + '{}'.format(vm_name))
    print(' Port Group'.ljust(20, '.') + '{}'.format(port_group))
    print(' CPUs'.ljust(20, '.') + '{}'.format(CPU))
    print(' Memory'.ljust(20, '.') + '{}GB'.format(mb_to_gb(RAM)))
    print(' Disk'.ljust(20, '.') + '{}GB'.format(convert_kb_to_gb(disk)))
    print(' Provision'.ljust(20, '.') + '{}'.format(provision))

    net_name  = select_network(datacenter, port_group)
    if create_vm(vm_folder, resource_pool, datastore, net_name, vm_name, CPU, RAM, disk, provision) == True:
        print('\nVM {} successfully created.\nDone.'.format(vm_name))

if __name__ == "__main__":
    main()