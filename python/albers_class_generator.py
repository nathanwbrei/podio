#!/usr/bin/env python
import os
import string
import sys
import pickle
import yaml
thisdir = os.path.dirname(os.path.abspath(__file__))

_text_ = """






  ALBERS Data Model
  =================

  Used
    %s
  to create
    %s classes
  in
    %s/

  Read instructions in
  the HOWTO.TXT to run
  your first example!

"""

class ClassGenerator(object):

  def __init__(self,yamlfile, install_dir, package_name, verbose = True):
    self.yamlfile = yamlfile
    self.install_dir = install_dir
    self.package_name =package_name
    self.template_dir = os.path.join(thisdir,"../templates")
    self.verbose=verbose
    self.buildin_types = ["int","float","double","unsigned int","unsigned"]
    self.created_classes = []
    self.requested_classes = []

  def process(self):
    stream = open(self.yamlfile, "r")
    content = yaml.load(stream)
    if content.has_key("components"):
      self.process_components(content["components"])
    if content.has_key("datatypes"):
      self.process_datatypes(content["datatypes"])
    self.create_selection_xml()
    self.print_report()

  def process_components(self,content):
    for name in content.iterkeys():
      self.requested_classes.append(name)
    for name, components in content.iteritems():
      self.create_component(name, components)

  def process_datatypes(self,content):
    for name in content.iterkeys():
      self.requested_classes.append(name)
      self.requested_classes.append("%sData" %name)
    for name, components in content.iteritems():
      if not components.has_key("members"):
        components["members"] = []
      self.create_data(name, components)
      self.create_class(name, components)
      self.create_collection(name, components)
      self.create_obj(name, components)

  def print_report(self):
    if self.verbose:
      pkl = open(os.path.join(thisdir,"figure.txt"))
      figure = pickle.load(pkl)
      text = _text_ % (self.yamlfile,
                       len(self.created_classes),
                       self.install_dir
                      )
      for i, line in enumerate(figure):
        print
        print line+text.splitlines()[i],
      print "     'Homage to the Square' - Josef Albers"
      print

  def create_selection_xml(self):
      content = ""
      for klass in self.created_classes:
        #if not klass.endswith("Collection") or klass.endswith("Data"):
          content += '          <class name="std::vector<%s>" />\n' %klass
          content += """
          <class name="%s">
            <field name="m_registry" transient="true"/>
            <field name="m_container" transient="true"/>
          </class>\n""" %klass

      templatefile = os.path.join(self.template_dir,"selection.xml.template")
      template = open(templatefile,"r").read()
      content = string.Template(template).substitute({"classes" : content})
      self.write_file("selection.xml",content)

  def prepare_for_writing_body(self, members):
      handles = []
      for member in members:
        name = member["name"]
        klass = member["type"]
        if klass.endswith("Handle"):
            handles.append(name)
      prepareforwriting = ""
      if (len(handles) !=0):
        prepareforwriting = "  for(auto& data : *m_data){\n %s  }"
        handleupdate = ""
        for handle in handles:
          handleupdate+= "    data.%s.prepareForWrite(registry);\n" %handle
        prepareforwriting= prepareforwriting % handleupdate
      return prepareforwriting

  def create_data(self, classname, definition):
    # check whether all member types are known
    # and prepare include directives
    includes = ""
    description = definition["description"]
    author      = definition["author"]
    members = definition["members"]
    for member in members:
      klass = member["type"]
      if klass in self.buildin_types:
        pass
      elif klass in self.requested_classes:
    #    includes += '#include "%s/%s.h"\n' %(self.package_name,klass)
        includes += '#include "%s.h"\n' %(klass)
      else:
        raise Exception("'%s' defines a member of a type '%s' that is not (yet) declared!" %(classname, klass))
    membersCode = ""
    for member in members:
      name = member["name"]
      klass = member["type"]
      description = member["description"]
      membersCode+= "  %s %s; ///%s \n" %(klass, name, description)

    # now handle the one-to-many relations
    refvectors = []
    if definition.has_key("OneToManyRelations"):
      refvectors = definition["OneToManyRelations"]
    for refvector in refvectors:
      name = refvector["name"]
      membersCode+= "  unsigned int %s_begin; \n" %(name)
      membersCode+= "  unsigned int %s_end; \n" %(name)

    substitutions = {"includes" : includes,
                     "members"  : membersCode,
                     "name"     : classname,
                     "description" : description,
                     "author"   : author,
                     "package_name" : self.package_name
    }
    self.fill_templates("Data",substitutions)
    self.created_classes.append(classname+"Data")

  def create_class(self, classname, definition):
    # check whether all member types are known
    # and prepare include directives
    includes = ""
    includes += '#include "%s.h"\n' %(classname+"Data")
    #includes += '#include "%s/%s.h"\n' %(self.package_name,classname+"Data")
    description = definition["description"]
    author      = definition["author"]
    members = definition["members"]
    for member in members:
      klass = member["type"]
      if klass in self.buildin_types:
        pass
      elif klass in self.requested_classes:
        #includes += '#include "%s/%s.h"\n' %(self.package_name,klass)
        includes += '#include "%s.h"\n' %(klass)
      else:
        raise Exception("'%s' defines a member of a type '%s' that is not declared!" %(classname, klass))

    # check one-to-many relations for consistency
    # and prepare include directives
    refvectors = []
    if definition.has_key("OneToManyRelations"):
      includes += "#include <vector>\n"
      refvectors = definition["OneToManyRelations"]
      for item in refvectors:
        klass = item["type"]
        if klass in self.requested_classes:
          includes += '#include "%s.h"\n' %klass
        else:
          raise Exception("'%s' declares a non-allowed many-relation to '%s'!" %(classname\
, klass))

    getter_implementations = ""
    setter_implementations = ""
    getter_declarations = ""
    setter_declarations = ""

    # handle standard members
    for member in members:
      name = member["name"]
      klass = member["type"]
      description = member["description"]
      getter_declarations+= "  const %s& %s() const { return m_obj->data.%s; };\n" %(klass, name, name)
      #getter_implementations+= "const %s& %s::%s() const { return m_obj->data.%s;}\n" %(klass, classname, name, name)
      if klass in self.buildin_types:
        setter_declarations += "  void %s(%s value) { m_obj->data.%s = value; };\n" %(name, klass, name)
        #setter_implementations += "void %s::%s(%s value){ m_obj->data.%s = value;}\n" %(classname, name, klass, name)
      else:
        setter_declarations += "  void %s(class %s value);\n" %(name, klass)
        setter_implementations += "void %s::%s(class %s value){ m_obj->data.%s = value;}\n" %(classname, name, klass, name)

    # handle one-to-many relations
    references_members = ""
    references_declarations = ""
    references = ""
    templatefile = os.path.join(self.template_dir,"RefVector.cc.template")
    references_template = open(templatefile,"r").read()
    templatefile = os.path.join(self.template_dir,"RefVector.h.template")
    references_declarations_template = open(templatefile,"r").read()
    for refvector in refvectors:
      substitutions = {"relation" : refvector["name"],
                       "relationtype" : refvector["type"],
                       "classname" : classname,
                       "package_name" : self.package_name
                      }
      references_declarations += string.Template(references_declarations_template).substitute(substitutions)
      references += string.Template(references_template).substitute(substitutions)
      references_members += "std::vector<%s>* m_%s; //! transient \n" %(refvector["type"], refvector["name"])

    substitutions = {"includes" : includes,
                     #"getters"  : getter_implementations,
                     "getter_declarations": getter_declarations,
                     "setters"  : setter_implementations,
                     "setter_declarations": setter_declarations,
                     "name"     : classname,
                     "description" : description,
                     "author"   : author,
                     "relations" : references,
                     "relation_declarations" : references_declarations,
                     "relation_members" : references_members,
                     "package_name" : self.package_name
                    }
    self.fill_templates("Object",substitutions)
    self.created_classes.append(classname)

  def create_collection(self, classname, definition):
    members = definition["members"]
    constructorbody = ""
    prepareforwritinghead = ""
    prepareforwritingbody = self.prepare_for_writing_body(members)
    vectorized_access_decl, vectorized_access_impl = self.prepare_vectorized_access(classname,members)
    setreferences = ""
    prepareafterread = ""
    # handle one-to-many-relations
    includes = ""
    initializers = ""
    relations = ""
    create_relations = ""
    clear_relations  = ""
    if definition.has_key("OneToManyRelations"):
      refvectors = definition["OneToManyRelations"]
      # member initialization
      constructorbody += "  m_refCollections = new albers::CollRefCollection();\n"
      clear_relations += "  for (auto& pointer : (*m_refCollections)) {pointer->clear(); }\n"
      for counter, item in enumerate(refvectors):
        name  = item["name"]
        klass = item["type"]
        substitutions = { "counter" : counter,
                          "class" : klass,
                          "name"  : name }
        # includes
        includes += '#include "%sCollection.h" \n' %(klass)
        # members
        relations += "  std::vector<%s>* m_rel_%s; //relation buffer for r/w\n" %(klass, name)
        relations += "  std::vector<std::vector<%s>*> m_rel_%s_tmp;\n " %(klass, name)
        # constructor calls
        initializers += ",m_rel_%s(new std::vector<%s>())" %(name, klass)
        constructorbody += "  m_refCollections->push_back(new std::vector<albers::ObjectID>());\n"
        # relation handling in ::create
        create_relations += "  auto %s_tmp = new std::vector<%s>();\n" %(name, klass)
        create_relations += "  m_rel_%s_tmp.push_back(%s_tmp);\n" %(name,name)
        create_relations += "  obj->m_%s = %s_tmp;\n" %(name, name)
        # relation handling in ::clear
        clear_relations += "  // clear relations to %s. Make sure to unlink() the reference data as they may be gone already\n" %(name)
        clear_relations += "  for (auto& pointer : m_rel_%s_tmp) {for(auto& item : (*pointer)) {item.unlink();}; delete pointer;}\n" %(name)
        clear_relations += "  m_rel_%s_tmp.clear();\n" %(name)
        clear_relations += "  for (auto& item : (*m_rel_%s)) {item.unlink(); }\n" %(name)
        clear_relations += "  m_rel_%s->clear();\n" %(name)
        # relation handling in ::prepareForWrite
        prepareforwritingbody += self.evaluate_template("CollectionPrepareForWriting.cc.template",substitutions)
        # relation handling in ::settingReferences
        setreferences += self.evaluate_template("CollectionSetReferences.cc.template",substitutions)

        prepareafterread += "    obj->m_%s = m_rel_%s;" %(name, name)

    substitutions = { "name" : classname,
                      "constructorbody" : constructorbody,
                      "prepareforwritinghead" : prepareforwritinghead,
                      "prepareforwritingbody" : prepareforwritingbody,
                      "setreferences" : setreferences,
                      "prepareafterread" : prepareafterread,
                      "includes" : includes,
                      "initializers" : initializers,
                      "relations"           : relations,
                      "create_relations" : create_relations,
                      "clear_relations"  : clear_relations,
                      "package_name" : self.package_name,
                      "vectorized_access_declaration" : vectorized_access_decl,
                      "vectorized_access_implementation" : vectorized_access_impl
    }
    self.fill_templates("Collection",substitutions)
    self.created_classes.append("%sCollection"%classname)

  def create_component(self, classname, components):
    """ Create a component class to be used within the data types
        Components can only contain simple data types and no user
        defined ones
    """
    for klass in components.itervalues():
      if klass in self.buildin_types:
        pass
      else:
        raise Exception("'%s' defines a member of a type '%s' which is not allowed in a component!" %(classname, klass))
    members = ""
    for name, klass in components.iteritems():
      members+= "  %s %s;\n" %(klass, name)
    substitutions = {"members"  : members,
                     "name"     : classname,
                     "package_name" : self.package_name
    }
    self.fill_templates("Component",substitutions)
    self.created_classes.append(classname)

  def create_obj(self, classname, definition):
    """ Create an obj class containing all information
        relevant for a given object.
    """
    relations = ""
    includes = ""
    deletereferences = ""
    if definition.has_key("OneToManyRelations"):
      refvectors = definition["OneToManyRelations"]
    else:
      refvectors = []
    for item in refvectors:
      name  = item["name"]
      klass = item["type"]
      relations += "  std::vector<%s>* m_%s;\n" %(klass, name)
      includes += '#include "%s.h"\n' %(klass)
      deletereferences += "delete m_%s;\n" %(name)
    substitutions = { "name" : classname,
                      "includes" : includes,
                      "relations" : relations,
                      "deletereferences" : deletereferences
    }
    self.fill_templates("Obj",substitutions)
    self.created_classes.append(classname+"Obj")

  def prepare_vectorized_access(self, classname,members ):
    implementation = ""
    declaration = ""
    for member in members:
      name = member["name"]
      klass = member["type"]
      substitutions = { "classname" : classname,
                       "member"    : name,
                       "type"      : klass
                       }
      implementation += self.evaluate_template("CollectionReturnArray.cc.template", substitutions)
      declaration += "  template<size_t arraysize>  \n  const std::array<%s,arraysize> %s() const;\n" %(klass, name)
    return declaration, implementation

  def write_file(self, name,content):
    #dispatch headers to header dir, the rest to /src
    fullname = os.path.join(self.install_dir,self.package_name,name)
    #if name.endswith("h"):
    #  fullname = os.path.join(self.install_dir,self.package_name,name)
    #else:
    #  fullname = os.path.join(self.install_dir,"src",name)
    open(fullname, "w").write(content)

  def evaluate_template(self, filename, substitutions):
      """ reads in a given template, evaluates it
          and returns result
      """
      templatefile = os.path.join(self.template_dir,filename)
      template = open(templatefile,"r").read()
      return string.Template(template).substitute(substitutions)

  def fill_templates(self, category,substitutions):
    # "Data" denotes the real class;
    # only headers and the FN should not contain Data
    if category == "Data":
      FN = "Data"
      endings = ("h")
    elif category == "Obj":
      FN = "Obj"
      endings = ("h","cc")
    elif category == "Component":
      FN = ""
      endings = ("h")
    elif category == "Object":
      FN = ""
      endings = ("h","cc")
    else:
      FN = category
      endings = ("h","cc")
    for ending in endings:
      templatefile = "%s.%s.template" %(category,ending)
      templatefile = os.path.join(self.template_dir,templatefile)
      template = open(templatefile,"r").read()
      content = string.Template(template).substitute(substitutions)
      filename = "%s%s.%s" %(substitutions["name"],FN,ending)
      self.write_file(filename,content)


class YAMLValidator(object):
  pass

##########################
if __name__ == "__main__":

  from optparse import OptionParser


  usage = """usage: %prog [options] <description.yaml> <targetdir> <packagename>

    Given a <description.yaml>
    it creates data classes
    and a LinkDef.h file in
    the specified <targetdir>:
      <packagename>/*.h
      src/*.cc
"""
  parser = OptionParser(usage)
  parser.add_option("-q", "--quiet",
                    action="store_false", dest="verbose", default=True,
                    help="Don't write a report to screen")
  (options, args) = parser.parse_args()

  if len(args) != 3:
      parser.error("incorrect number of arguments")

  gen = ClassGenerator(args[0], args[1], args[2], verbose = options.verbose)
  gen.process()
