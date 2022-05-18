#!/usr/bin/env python3
# ===============================================================================
# NAME: XmlEnumParser.py
#
# DESCRIPTION: This class parses the XML Enum types files.
#
# USAGE:
#
# AUTHOR: reder
# EMAIL:  reder@jpl.nasa.gov
# DATE CREATED  : April 6, 2018
#
# Copyright 2018, California Institute of Technology.
# ALL RIGHTS RESERVED. U.S. Government Sponsorship acknowledged.
# ===============================================================================
#
# Python standard modules
#
import logging
import os
import sys

from fprime_ac.parsers import XmlParser
from fprime_ac.utils import ConfigManager
from fprime_ac.utils.exceptions import (
    FprimeRngXmlValidationException,
    FprimeXmlException,
)
from lxml import etree, isoschematron

#
# Python extension modules and custom interfaces
#

#
# Universal globals used within module go here.
# (DO NOT USE MANY!)
#
# Global logger init. below.
PRINT = logging.getLogger("output")
DEBUG = logging.getLogger("debug")
ROOTDIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "..")
#
class XmlEnumParser:
    """
    An XML parser class that uses lxml.etree to consume an XML
    enum type documents.  The class is instanced with an XML file name.
    """

    def __init__(self, xml_file=None):
        """
        Given a well formed XML file (xml_file), read it and turn it into
        a big string.
        """
        self.__name = ""
        self.__namespace = None
        self.__default = None
        self.__serialize_type = None

        self.__xml_filename = xml_file
        self.__items = []
        self.__comment = None

        self.Config = ConfigManager.ConfigManager.getInstance()

        if os.path.isfile(xml_file) == False:
            stri = f"ERROR: Could not find specified XML file {xml_file}."
            raise OSError(stri)
        with open(xml_file) as fd:
            xml_file = os.path.basename(xml_file)
            self.__xml_filename = xml_file
            self.__items = []

            xml_parser = etree.XMLParser(remove_comments=True)
            element_tree = etree.parse(fd, parser=xml_parser)
        with open(ROOTDIR + self.Config.get("schema", "enum")) as relax_file_handler:
            relax_parsed = etree.parse(relax_file_handler)
        relax_compiled = etree.RelaxNG(relax_parsed)

        self.validate_xml(xml_file, element_tree, "schematron", "enum_value")

        self.check_enum_values(element_tree)

        # 2/3 conversion
        if not relax_compiled.validate(element_tree):
            raise FprimeRngXmlValidationException(relax_compiled.error_log)

        enum = element_tree.getroot()
        if enum.tag != "enum":
            PRINT.info(f"{xml_file} is not an enum definition file")
            sys.exit(-1)

        print(f'Parsing Enum {enum.attrib["name"]}')
        self.__name = enum.attrib["name"]

        if "namespace" in enum.attrib:
            self.__namespace = enum.attrib["namespace"]
        else:
            self.__namespace = None

        self.__default = enum.attrib["default"] if "default" in enum.attrib else None
        if "serialize_type" in enum.attrib:
            self.__serialize_type = enum.attrib["serialize_type"]
        else:
            self.__serialize_type = None

        for enum_tag in enum:
            if enum_tag.tag == "comment":
                self.__comment = enum_tag.text
            elif enum_tag.tag == "item":
                item = enum_tag.attrib
                if "comment" not in item:
                    item["comment"] = ""
                self.__items.append((item["name"], item["value"], item["comment"]))
                if "value" not in item:
                    item["value"] = ""

    def validate_xml(self, dict_file, parsed_xml_tree, validator_type, validator_name):
        # Check that validator is valid
        if not self.Config.has_option(validator_type, validator_name):
            msg = (
                "XML Validator type "
                + validator_type
                + " not found in ConfigManager instance"
            )
            raise FprimeXmlException(msg)

        with open(
            ROOTDIR + self.Config.get(validator_type, validator_name)
        ) as validator_file_handler:
            validator_parsed = etree.parse(validator_file_handler)
        if validator_type == "schema":
            validator_compiled = etree.RelaxNG(validator_parsed)
        elif validator_type == "schematron":
            validator_compiled = isoschematron.Schematron(validator_parsed)

        # Validate XML file
        if not validator_compiled.validate(parsed_xml_tree):
            if validator_type == "schema":
                msg = f"XML file {dict_file} is not valid according to {validator_type} {ROOTDIR + self.Config.get(validator_type, validator_name)}."

                raise FprimeXmlException(msg)
            elif validator_type == "schematron":
                msg = f"WARNING: XML file {dict_file} is not valid according to {validator_type} {ROOTDIR + self.Config.get(validator_type, validator_name)}."

                PRINT.info(msg)

    def check_enum_values(self, element_tree):
        """
        Raises exception in case that enum items are inconsistent
        in whether they include attribute 'value'
        """
        if not self.is_attribute_consistent(element_tree, "value"):
            msg = "If one enum item has a value attribute, all items should have a value attribute"
            raise FprimeXmlException(msg)

    def is_attribute_consistent(self, element_tree, val_name):
        """
        Returns true if either all or none of the enum items
        contain a given value
        """
        has_value = 0
        total = 0
        for enum_item in element_tree.iter():
            if enum_item.tag == "item":
                total += 1
                if val_name in enum_item.keys():
                    has_value += 1

        return has_value in [0, total]

    def get_max_value(self):
        # Assumes that items have already been checked for consistency,
        # self.__items stores a list of tuples with index 1 being the value
        if self.__items[0][1] != "":
            max_value = self.__items[0][1]

            for item in self.__items:
                max_value = max(max_value, item[1])

        else:
            max_value = str(len(self.__items) - 1)

        return max_value

    def get_name(self):
        return self.__name

    def get_namespace(self):
        return self.__namespace

    def get_default(self):
        return self.__default

    def get_serialize_type(self):
        return self.__serialize_type

    def get_items(self):
        return self.__items

    def get_comment(self):
        return self.__comment


if __name__ == "__main__":
    xmlfile = sys.argv[1]
    xml = XmlParser.XmlParser(xmlfile)
    print(f"Type of XML is: {xml()}")
    print(f"Enum XML parse test ({xmlfile})")
    xml_parser = XmlEnumParser(xmlfile)
    print(
        f"Enum name: {xml_parser.get_name()}, namespace: {xml_parser.get_namespace()}, default: {xml_parser.get_default()}, serialize_type: {xml_parser.get_serialize_type()}"
    )

    print("Items")
    for item in xml_parser.get_items():
        print("%s=%s // %s" % item)
