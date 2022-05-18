#!/usr/bin/env python3
# ===============================================================================
# NAME: TopoFactory.py
#
# DESCRIPTION: This is a factory class for instancing the topology
#              meta-model required.
#
# AUTHOR: reder
# EMAIL:  reder@jpl.nasa.gov
# DATE CREATED  : 10 July 2013
#
# Copyright 2013, California Institute of Technology.
# ALL RIGHTS RESERVED. U.S. Government Sponsorship acknowledged.
# ===============================================================================
#
# Python standard modules
#

import logging
import sys

from fprime_ac.models import Component, Port, Topology
from fprime_ac.parsers import XmlComponentParser
from fprime_ac.utils import ConfigManager
from fprime_ac.utils.buildroot import (
    BuildRootCollisionException,
    BuildRootMissingException,
    locate_build_root,
)

# from builtins import True
# from Canvas import Window


# Global logger init. below.
PRINT = logging.getLogger("output")
DEBUG = logging.getLogger("debug")


class TopoFactory:
    """
    This is a concrete factory method object used to create the interface
    to the code generation.  A single call to create is made that returns
    a the topology object containing a list of instanced components and
    general topology information. Each component contains a list
    of output ports and each output port contains target component instance
    name and port name and type.
    """

    __instance = None

    def __init__(self):
        """
        Private Constructor (singleton pattern)
        """
        self.__instance = None
        self.__config = ConfigManager.ConfigManager.getInstance()
        self.__generate_new_IDS = True  # Work around to disable ID generation/table output in the case AcConstants.ini is used to build

        self.__table_info = [
            ["INSTANCE NAME", 5, "Name of the instance object."],
            ["BASE ID (HEX)", 0, "Base ID set for the instance."],
            [
                "REQUESTED WINDOW SIZE",
                0,
                "Specified by either the 'base_id_range' attribute in the instance tag or by finding the max of the 'base_id_range' attribute in the topology tag and the largest internal ID of the instance.",
            ],
            [
                "DIFFERENCED ID WINDOW SIZE",
                0,
                "Calculated by subtracting the current base ID from the next base ID.",
            ],
            [
                "LARGEST COMPONENT INTERNAL ID",
                0,
                "The largest ID found in the events, channels, and commands of the instance.",
            ],
            [
                "MAX AMOUNT OF IDS",
                0,
                "The largest amount of items from either events, channels, or commands.",
            ],
        ]

    def set_generate_ID(self, value):
        """
        If value is true, new IDs will be generated using the topology model and the internal algorithm
        If value is false, IDs will not be generated and will not be used inside the cpp file
        """
        self.__generate_new_IDS = value

    def getInstance():
        """
        Return instance of singleton.
        """
        if TopoFactory.__instance is None:
            TopoFactory.__instance = TopoFactory()

        return TopoFactory.__instance

    # define static method
    getInstance = staticmethod(getInstance)

    def create(self, the_parsed_topology_xml, generate_list_file=True):
        """
        Create a topology model here.
        """
        # Instance a list of model.Component classes that are all the instanced items from parsed xml.
        x = the_parsed_topology_xml

        componentXMLNameToComponent = (
            {}
        )  # Dictionary maps XML names to processes component objects so redundant processing is avoided
        components = []
        for comp_xml_path in x.get_comp_type_file_header_dict():
            try:
                file_path = locate_build_root(comp_xml_path)
            except (BuildRootMissingException, BuildRootCollisionException) as bre:
                stri = f"ERROR: Could not find XML file {comp_xml_path}. {str(bre)}"
                raise OSError(stri)
            processedXML = XmlComponentParser.XmlComponentParser(file_path)
            comp_name = processedXML.get_component().get_name()
            componentXMLNameToComponent[comp_name] = processedXML

        for instance in x.get_instances():
            if instance.get_type() not in list(componentXMLNameToComponent.keys()):
                PRINT.info(
                    f"Component XML file type {instance.get_type()} was not specified in the topology XML. Please specify the path using <import_component_type> tags."
                )

            else:
                instance.set_component_object(
                    componentXMLNameToComponent[instance.get_type()]
                )
            components.append(
                Component.Component(
                    instance.get_namespace(),
                    instance.get_name(),
                    instance.get_type(),
                    xml_filename=x.get_xml_filename(),
                    kind2=instance.get_kind(),
                )
            )

        # print "Assembly name: " + x.get_name(), x.get_base_id(), x.get_base_id_window()
        # for component in components:
        #    print component.get_name(), component.get_base_id(), component.get_base_id_window()

        if self.__generate_new_IDS:
            # Iterate over all the model.Component classes and...
            instance_name_base_id_list = self.__compute_base_ids(
                x.get_base_id(),
                x.get_base_id_window(),
                x.get_instances(),
                x.get_xml_filename(),
                generate_list_file,
            )
        else:
            instance_name_base_id_list = []

        # Iterate over all the model.Component classes and then...
        # Iterate over all the connection sources and assigned output ports to each Component..
        # For each output port you want to assign the connect comment, target component name, target port and type...
        #    (Requires adding to the model.Port class ether members or a member called of type TargetConnection)
        for component in components:
            port_obj_list = []
            for connection in x.get_connections():
                if component.get_name() == connection.get_source()[0]:
                    port = Port.Port(
                        connection.get_source()[1],
                        connection.get_source()[2],
                        None,
                        None,
                        comment=connection.get_comment(),
                        xml_filename=x.get_xml_filename,
                    )
                    port.set_source_num(connection.get_source()[3])
                    port.set_target_comp(connection.get_target()[0])
                    port.set_target_port(connection.get_target()[1])
                    port.set_target_type(connection.get_target()[2])
                    port.set_target_num(connection.get_target()[3])
                    if connection.get_source()[1].startswith("i"):
                        port.set_direction("input")
                    else:
                        port.set_direction("output")
                    if connection.get_target()[1].startswith("i"):
                        port.set_target_direction("input")
                    else:
                        port.set_target_direction("output")

                    port_obj_list.append(port)
            component.set_ports(port_obj_list)

        # Instance a Topology class and give it namespace, comment and list of components.
        the_topology = Topology.Topology(
            x.get_namespace(),
            x.get_comment(),
            components,
            x.get_name(),
            instance_name_base_id_list,
            x.get_prepend_instance_name(),
        )
        the_topology.set_instance_header_dict(x.get_comp_type_file_header_dict())

        return the_topology

    def __id_to_int(self, id_string):
        """
        Converts ID to int. If the item is hex, it will be converted to an base 10 int.
        """
        try:
            out = int(float(id_string))
        except (TypeError, ValueError):
            out = int(id_string, 16)

        return out

    def __compute_component_base_id_range(self, comp_xml):
        """
        Computes the base ID range of an XMLComponentParser object.
        """
        if not comp_xml:
            return None
        highest_ID = None

        event_id_list = []
        for event in comp_xml.get_events():
            # if len(event.get_ids()) != 1:
            #   print("Component of type {} has multiple IDs for event {}. Please check if the ACConstants.ini file has all the ids set to zero.".format(comp_xml.get_component().get_name() , event.get_name()))
            id = self.__id_to_int(event.get_ids()[0])

            if id in event_id_list:
                print(
                    f"IDCollisionError: Event ID {id} in component {comp_xml.get_component().get_name()} is used more than once in the same component."
                )

                sys.exit(-1)
            event_id_list.append(id)

            if highest_ID is None or id > highest_ID:
                highest_ID = id

        channel_id_list = []
        for channel in comp_xml.get_channels():
            # if len(event.get_ids()) != 1:
            #   print("Component of type {} has multiple IDs for event {}. Please check if the ACConstants.ini file has all the ids set to zero.".format(comp_xml.get_component().get_name() , event.get_name()))
            id = self.__id_to_int(channel.get_ids()[0])

            if id in channel_id_list:
                print(
                    f"IDCollisionError: Channel ID {id} in component {comp_xml.get_component().get_name()} is used more than once in the same component."
                )

                sys.exit(-1)
            channel_id_list.append(id)

            if highest_ID is None or id > highest_ID:
                highest_ID = id

        command_id_list = []
        for commands in comp_xml.get_commands():
            # if len(event.get_ids()) != 1:
            #   print("Component of type {} has multiple IDs for event {}. Please check if the ACConstants.ini file has all the ids set to zero.".format(comp_xml.get_component().get_name() , event.get_name()))
            id = self.__id_to_int(commands.get_opcodes()[0])

            if id in command_id_list:
                print(
                    f"IDCollisionError: Command ID {id} in component {comp_xml.get_component().get_name()} is used more than once in the same component."
                )

                sys.exit(-1)
            command_id_list.append(id)

            if highest_ID is None or id > highest_ID:
                highest_ID = id

        parameter_id_list = []
        parameter_opcode_list = []
        for parameters in comp_xml.get_parameters():
            # if len(event.get_ids()) != 1:
            #   print("Component of type {} has multiple IDs for event {}. Please check if the ACConstants.ini file has all the ids set to zero.".format(comp_xml.get_component().get_name() , event.get_name()))
            # Check ids
            id = self.__id_to_int(parameters.get_ids()[0])

            if id in parameter_id_list:
                print(
                    f"IDCollisionError: Parameter ID {id} in component {comp_xml.get_component().get_name()} is used more than once in the same component."
                )

                sys.exit(-1)
            parameter_id_list.append(id)

            if highest_ID is None or id > highest_ID:
                highest_ID = id

            # check set/save op and make sure they don't collide with command IDs
            # Set opcodes

            id = self.__id_to_int(parameters.get_set_opcodes()[0])

            if id in parameter_opcode_list:
                print(
                    f"IDCollisionError: Parameter set opcode {id} in component {comp_xml.get_component().get_name()} is used more than once in the same component."
                )

                sys.exit(-1)
            if id in command_id_list:
                print(
                    f"IDCollisionError: Parameter set opcode {id} in component {comp_xml.get_component().get_name()} is the same as another command id in this component."
                )

                sys.exit(-1)
            parameter_opcode_list.append(id)

            if highest_ID is None or id > highest_ID:
                highest_ID = id

            # Save opcodes

            id = self.__id_to_int(parameters.get_save_opcodes()[0])

            if id in parameter_opcode_list:
                print(
                    f"IDCollisionError: Parameter save opcode {id} in component {comp_xml.get_component().get_name()} is used more than once in the same component."
                )

                sys.exit(-1)
            if id in command_id_list:
                print(
                    f"IDCollisionError: Parameter save opcode {id} in component {comp_xml.get_component().get_name()} is the same as another command id in this component."
                )

                sys.exit(-1)
            parameter_opcode_list.append(id)

            if highest_ID is None or id > highest_ID:
                highest_ID = id

        if highest_ID is not None:
            return highest_ID + 1

    def __compute_component_ID_amount(self, comp_xml):
        """
        Computes the max amount of IDs found in an XMLComponentParser object.
        """
        return (
            max(
                len(comp_xml.get_events()),
                len(comp_xml.get_channels()) + 2 * len(comp_xml.get_parameters()),
                len(comp_xml.get_commands()),
                len(comp_xml.get_parameters()),
            )
            if comp_xml
            else None
        )

    def __compute_base_ids(
        self,
        assembly_base_id,
        assembly_window,
        instances,
        xml_file_path,
        generate_list_file,
    ):
        """
        Compute the set of baseIds for the component instances here.
        @param components: List of Component object instances with baseId, window, and max window size set
        @return: List of tuples of form (instance name, base id, window size)
        """
        # Assign the assembly baseId and window size or use default if none exists
        if assembly_base_id is None:
            assembly_base_id = self.__config.get("assembly", "baseID")
            PRINT.info(
                f"WARNING: No assembly base Id set, defaulting to {assembly_base_id}"
            )

        if assembly_window is None:
            assembly_window = self.__config.get("assembly", "window")
            PRINT.info(
                f"WARNING: No assembly base Id window size set, defaulting to {assembly_window}"
            )


        out_base_ids_list = []

        assembly_base_id = int(assembly_base_id)
        assembly_window = int(assembly_window)

        initial_comp_with_ID = (
            []
        )  # List of component tuples that have base IDS specified in the topology model
        initial_comp_without_ID = (
            []
        )  # Lit of component tuples that do not have base IDS specified in the topology model

        id = assembly_base_id
        if id <= 0:
            id = 1
        window = assembly_window

        # Pass 1 - Populate initial_comp lists with their respective items

        for inst in instances:
            t = self.__set_base_id_list(id, window, inst)
            if inst.get_base_id() is None:
                initial_comp_without_ID.append(t)
            else:
                initial_comp_with_ID.append(t)

        # Pass 2 - Sort with_ID list by base ID and without_ID list by window size

        initial_comp_with_ID.sort(key=lambda x: x[1])
        initial_comp_without_ID.sort(key=lambda x: x[2])

        # Pass 3 - Check with_ID list to ensure no base / window IDS collide

        prev_id = 0
        prev_window = 0
        prev_name = "NONE"
        for t in initial_comp_with_ID:
            if t[1] < prev_id + prev_window:
                err = f"Component {t[0]} has a base ID {t[1]} which collides with the allocated IDs for component {prev_name} (base ID {prev_id} , window ID {prev_window})"

                PRINT.info(err)
                raise Exception(err)
            # Code below auto adjusts user specified IDS
            # if(t[1] < prev_id + prev_window):
            #    t[1] = prev_id + prev_window
            prev_name = t[0]
            prev_id = t[1]
            prev_window = t[2]

        # Pass 4 - Merge ID lists

        prev_id = id
        prev_window = 0
        with_ID_obj = None
        without_ID_obj = None
        while not (
            not initial_comp_with_ID
            and not initial_comp_without_ID
            and not with_ID_obj
            and not without_ID_obj
        ):
            if initial_comp_with_ID and with_ID_obj is None:
                with_ID_obj = initial_comp_with_ID.pop(0)

            if initial_comp_without_ID and without_ID_obj is None:
                without_ID_obj = initial_comp_without_ID.pop(0)

            next_poss_id = (
                prev_id + prev_window
            )  # The next possible id that can be taken

            if (
                with_ID_obj is None and without_ID_obj is not None
            ):  # If there is nothing in the with ID list, but items exist in the without ID list
                without_ID_obj[1] = next_poss_id
                out_base_ids_list.append(without_ID_obj)
                without_ID_obj = None
            elif (
                with_ID_obj is not None and without_ID_obj is None
            ):  # If items exist in the with  ID list but don't in the without ID list
                out_base_ids_list.append(with_ID_obj)
                with_ID_obj = None
            elif next_poss_id + without_ID_obj[2] <= with_ID_obj[1]:
                without_ID_obj[1] = next_poss_id
                out_base_ids_list.append(without_ID_obj)
                without_ID_obj = None
            else:
                out_base_ids_list.append(with_ID_obj)
                with_ID_obj = None

            prev_id = out_base_ids_list[-1][1]
            prev_window = out_base_ids_list[-1][2]

        # Pass 5 - Save and Print table
        save_buffer = ""

        prev = None
        act_wind = 0
        for t in out_base_ids_list:
            if prev is not None:
                # pylint: disable=E1136
                act_wind = t[1] - prev[1]
            save_buffer = self.__print_base_id_table(prev, act_wind, save_buffer)
            prev = t
        save_buffer = self.__print_base_id_table(prev, "inf.", save_buffer)

        save_buffer = self.__print_base_id_table_comments(save_buffer)

        if generate_list_file:
            csv_removed_from_path_name = xml_file_path.replace(".XML", "")
            csv_removed_from_path_name = csv_removed_from_path_name.replace(".xml", "")

            save_log_file_path = f"{csv_removed_from_path_name}_IDTableLog.txt"

            with open(save_log_file_path, "w") as save_log_file:
                save_log_file.write(save_buffer)
        return out_base_ids_list

    def __print_base_id_table_comments(self, save_buffer):
        # First find the table length and the largest length of a column header
        tableSize = 0
        largestColHeader = 0
        for header in self.__table_info:
            headerLen = len(header[0])
            tableSize += headerLen + 2 * header[1]
            if headerLen > largestColHeader:
                largestColHeader = headerLen

        print_item = "-" * (tableSize + 4)
        PRINT.info(print_item)
        save_buffer += print_item + "\n"

        tabLen = largestColHeader + 3
        for header in self.__table_info:
            headerLen = len(header[0])
            desc = header[0] + " " * (largestColHeader - headerLen) + " - " + header[2]
            firstRun = True
            while desc != "":
                if firstRun:
                    outString = desc[:tableSize]
                    desc = desc[tableSize:]
                    firstRun = False
                else:
                    newSize = tableSize - tabLen
                    outString = " " * tabLen + desc[:newSize]
                    desc = desc[newSize:]
                print_item = (f"| {outString}" + (tableSize - len(outString)) * " " + " |")
                PRINT.info(print_item)
                save_buffer += print_item + "\n"

        print_item = "-" * (tableSize + 4)
        PRINT.info(print_item)
        save_buffer += print_item + "\n"

        return save_buffer

    def __print_base_id_table(self, base_id_tuple, actual_window_size, save_buffer):
        """
        Routing prints the base_id_list to a table format.
        If base_id_list is None, the routing prints the header
        """

        if base_id_tuple is None:
            print_item = " | ".join(
                header[1] * " " + header[0] + header[1] * " "
                for header in self.__table_info
            )
            save_buffer += print_item + "\n"
            PRINT.info(print_item)

        else:
            ns = " (D)" if base_id_tuple[3].get_base_max_id_window() is None else ""
            data_row = [
                str(base_id_tuple[0]),
                f"{str(base_id_tuple[1])} ({hex(base_id_tuple[1])})",
                str(base_id_tuple[2]) + ns,
                str(actual_window_size),
                str(base_id_tuple[4]),
                str(base_id_tuple[5]),
            ]

            table_header_size = [
                len(header[0]) + 2 * header[1] for header in self.__table_info
            ]

            while True:
                all_items_length_zero = all(len(data_item) == 0 for data_item in data_row)
                if all_items_length_zero:
                    break

                row_string = ""
                for i in range(len(self.__table_info)):
                    curr_write_string = data_row[i][:table_header_size[i]]
                    data_row[i] = data_row[i][table_header_size[i] :]
                    if i != 0:
                        row_string += " | "
                    format_string = "{0:^" + str(table_header_size[i]) + "}"
                    row_string += format_string.format(curr_write_string)

                save_buffer += row_string + "\n"
                PRINT.info(row_string)
        return save_buffer

    def __set_base_id_list(self, id, size, inst):
        """
        Routine to set up the base id and window size with actual or instance set values.
        Routine also checks window size against component max IDs needed if they are found.
        """
        comp = inst.get_component_object()
        # set instance name
        n = inst.get_name()
        #
        """
        Logic for calculating base ids
        1) If the user did not specify the base ID within an instance, set it to None
        2) If the user did specify the base ID within an instance, check if it is greater than the base ID for the entire topology
            a) if it is greater, use the base ID from the instance
            b) if it is not greater, add the base ID from the instance and the base ID from the topology model and use the sum
        """
        if inst.get_base_id() is None:
            b = None
        else:
            if id > abs(int(inst.get_base_id(), 0)):
                b = abs(int(inst.get_base_id(), 0)) + id
                PRINT.info(
                    f"WARNING: {n} instance adding instance supplied base ID to the topology supplied base ID (New ID is {b}) because instance supplied base ID is smaller than the topology supplied base ID."
                )

            else:
                b = abs(int(inst.get_base_id(), 0))
            PRINT.info("WARNING: %s instance resetting base id to %d" % (n, b))
        #
        # set window size or override it on instance basis

        component_calculated_window_range = self.__compute_component_base_id_range(comp)

        """
        Note: The calculated window range is really the largest ID (plus one) found in the component object.

        Logic for calculating window size
        1) If user specifies window size in instance tag, use that.
        2) If the user does not specify the window size in the instance tag, use the larger of the default window size and the calculated window size
        3) If the calculated window size is larger than the new window size, thrown an error
        """

        if inst.get_base_id_window() is not None:
            w = abs(int(inst.get_base_id_window(), 0))
            PRINT.info(
                f"{n} instance resetting base id window range to instance specified size ({w})"
            )

        elif size > component_calculated_window_range:
            w = size
            PRINT.info(
                f"{n} instance resetting base id window range to default topology size ({w})"
            )

        else:
            w = component_calculated_window_range
            PRINT.info(
                f"{n} instance resetting base id window range to size calculated from the component XML file ({w})"
            )


        if (
            component_calculated_window_range is not None
            and w < component_calculated_window_range
        ):
            PRINT.info(
                f"ERROR: The specified window range for component {n} is {w}, which is smaller than the calculated window range of {component_calculated_window_range}. Please check the instance definitions in the topology xml file."
            )


        return [
            n,
            b,
            w,
            inst,
            component_calculated_window_range,
            self.__compute_component_ID_amount(comp),
        ]
