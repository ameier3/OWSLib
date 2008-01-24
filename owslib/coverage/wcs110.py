# -*- coding: ISO-8859-15 -*-
# =============================================================================
# Copyright (c) 2004, 2006 Sean C. Gillies
# Copyright (c) 2007 STFC <http://www.stfc.ac.uk>
#
# Authors : 
#          Dominic Lowe <d.lowe@rl.ac.uk>
#
# Contact email: d.lowe@rl.ac.uk
# =============================================================================

##########NOTE: Does not conform to new interfaces yet #################

from wcsBase import WCSBase, WCSCapabilitiesReader, RereadableURL
from urllib import urlencode
from urllib2 import urlopen
from owslib.etree import etree
import os, errno
from owslib.coverage import wcsdecoder

def ns(tag):
    return '{http://www.opengis.net/wcs/1.1}'+tag

class ServiceException(Exception):
    pass

class WebCoverageService_1_1_0(WCSBase):
    """Abstraction for OGC Web Coverage Service (WCS), version 1.1.0
    Implements IWebCoverageService.
    """
    
    def __getitem__(self, name):
        ''' check contents dictionary to allow dict like access to service layers'''
        if 'servicecontents' in self.__dict__.keys():
            if name in self.__getattribute__('servicecontents').keys():
                return self.__getattribute__('servicecontents')[name]
        #otherwise behave normally:
        return self.__getattribute__(name)
    
    def __init__(self,url,xml):
        self.version='1.1.0'
        self.url = url   
        # initialize from saved capability document or access the server
        reader = WCSCapabilitiesReader(self.version)
        if xml:
            self._capabilities = reader.readString(xml)
        else:
            self._capabilities = reader.read(self.url)
            
        #build metadata objects:
        
        #serviceIdentification metadata
        elem=self._capabilities.find('{http://www.opengis.net/wcs/1.1/ows}ServiceIdentification')
        self.serviceidentification=ServiceIdentification(elem)
        
        #serviceProvider
        elem=self._capabilities.find('{http://www.opengis.net/ows}ServiceProvider')
        self.serviceprovider=ServiceProvider(elem)
                
        #serviceOperations
        self.serviceoperations = []
        for elem in self._capabilities.findall('{http://www.opengis.net/wcs/1.1/ows}OperationsMetadata/{http://www.opengis.net/wcs/1.1/ows}Operation/'):
            self.serviceoperations.append(Operation(elem))
        
        # exceptions - ***********TO DO *************
            self.exceptions = [f.text for f \
                in self._capabilities.findall('Capability/Exception/Format')]
              
        # serviceContents: our assumption is that services use a top-level layer
        # as a metadata organizer, nothing more.
        self.servicecontents = {}
        top = self._capabilities.find('{http://www.opengis.net/wcs/1.1}Contents/{http://www.opengis.net/wcs/1.1}CoverageSummary')
        for elem in self._capabilities.findall('{http://www.opengis.net/wcs/1.1}Contents/{http://www.opengis.net/wcs/1.1}CoverageSummary/{http://www.opengis.net/wcs/1.1}CoverageSummary'):                    
            cm=ContentMetadata(elem, top, self)
            self.servicecontents[cm.id]=cm
            
        if self.servicecontents=={}:
            #non-hierarchical.
            top=None
            for elem in self._capabilities.findall('{http://www.opengis.net/wcs/1.1}Contents/{http://www.opengis.net/wcs/1.1}CoverageSummary'):     
                cm=ContentMetadata(elem, top)
                #make the describeCoverage requests to populate the supported formats/crs attributes
                self.servicecontents[cm.id]=cm

    def items(self):
        '''supports dict-like items() access'''
        items=[]
        for item in self.servicecontents:
            items.append((item,self.servicecontents[item]))
        return items
        
        
    #TO DECIDE: May need something like this
    #def _getaddressString(self):
        #address=self.capabilities.serviceProvider.serviceContact.contactInfo.address.deliveryPoint
        #return address
          
    #TO DECIDE: Offer repackaging of coverageXML/Multipart MIME output?
    #def getData(self, directory='outputdir', outputfile='coverage.nc',  **kwargs):
        #u=self.getCoverageRequest(**kwargs)
        ##create the directory if it doesn't exist:
        #try:
            #os.mkdir(directory)
        #except OSError, e:
            ## Ignore directory exists error
            #if e.errno <> errno.EEXIST:
                #raise          
        ##elif wcs.version=='1.1.0':
        ##Could be multipart mime or XML Coverages document, need to use the decoder...
        #decoder=wcsdecoder.WCSDecoder(u)
        #x=decoder.getCoverages()
        #if type(x) is wcsdecoder.MpartMime:
            #filenames=x.unpackToDir(directory)
            ##print 'Files from 1.1.0 service written to %s directory'%(directory)
        #else:
            #filenames=x
        #return filenames
    
    #TO DO: Handle rest of the  WCS 1.1.0 keyword parameters e.g. GridCRS etc. 
    def getCoverage(self, identifier=None, bbox=None, time=None, format = None, store=False, rangesubset=None, gridbaseCRS=None, gridtype=None, gridCS=None, gridorigin=None, gridoffsets=None, method='Get',**kwargs):
        """Request and return a coverage from the WCS as a file-like object
        note: additional **kwargs helps with multi-version implementation
        core keyword arguments should be supported cross version
        example:
        cvg=wcs.getCoverageRequest(identifier=['TuMYrRQ4'], timeSequence=['2792-06-01T00:00:00.0'], bbox=(-112,36,-106,41),format='application/netcdf', store='true')

        is equivalent to:
        http://myhost/mywcs?SERVICE=WCS&REQUEST=GetCoverage&IDENTIFIER=TuMYrRQ4&VERSION=1.1.0&BOUNDINGBOX=-180,-90,180,90&TIMESEQUENCE=[bb&FORMAT=application/netcdf
        
        if store = true, returns a coverages XML file
        if store = false, returns a multipart mime
        """

        if method == 'Get':
            method='{http://www.opengis.net/wcs/1.1/ows}Get'
        base_url = self.__getOperationByName('GetCoverage').methods[method]['url']


        #process kwargs
        request = {'version': self.version, 'request': 'GetCoverage', 'service':'WCS'}
        assert len(identifier) > 0
        request['identifier']=identifier
        #request['identifier'] = ','.join(identifier)
        if bbox:
            request['boundingbox']=','.join([str(x) for x in bbox])
        if time:
            request['timesequence']=','.join(time)
        request['format']=format
        request['store']=store
        
        #rangesubset: untested - require a server implementation
        if rangesubset:
            request['RangeSubset']=rangesubset
        
        #GridCRS structure: untested - require a server implementation
        if gridbaseCRS:
            request['gridbaseCRS']=gridbaseCRS
        if gridtype:
            request['gridtype']=gridtype
        if gridCS:
            request['gridCS']=gridCS
        if gridorigin:
            request['gridorigin']=gridorigin
        if gridoffsets:
            request['gridoffsets']=gridoffsets
       
       #anything else e.g. vendor specific parameters must go through kwargs
        if kwargs:
            for kw in kwargs:
                request[kw]=kwargs[kw]
        
        #encode and request
        data = urlencode(request)
        data = urlencode(request)
        fullurl=base_url + '?' + data
        u=urlopen(fullurl)
                
        # check for service exceptions, and return
        if u.info()['Content-Type'] == 'text/xml':          
            #going to have to read the xml to see if it's an exception report.
            #wrap the url stram in a extended StringIO object so it's re-readable
            u=RereadableURL(u)      
            se_xml= u.read()
            se_tree = etree.fromstring(se_xml)
            serviceException=se_tree.find('{http://www.opengis.net/ows}Exception')
            if serviceException is not None:
                raise ServiceException, \
                str(serviceException.text).strip()
            u.seek(0)
        return u
        
        
    def __getOperationByName(self, name):
        """Return a named operation item."""
        for item in self.serviceoperations:
            if item.name == name:
                return item
        raise KeyError, "No operation named %s" % name
        
class Operation(object):
    """Abstraction for operation metadata    
    Implements IOperationMetadata.
    """
    def __init__(self, elem):
        self.name = elem.get('name')       
        self.formatOptions = [f.text for f in elem.findall('{http://www.opengis.net/wcs/1.1/ows}Parameter/{http://www.opengis.net/wcs/1.1/ows}AllowedValues/{http://www.opengis.net/wcs/1.1/ows}Value')]
        methods = []
        for verb in elem.findall('{http://www.opengis.net/wcs/1.1/ows}DCP/{http://www.opengis.net/wcs/1.1/ows}HTTP/*'):
            url = verb.attrib['{http://www.w3.org/1999/xlink}href']
            methods.append((verb.tag, {'url': url}))
        self.methods = dict(methods)

class ServiceIdentification(object):
    """ Abstraction for ServiceIdentification Metadata 
    implements IServiceIdentificationMetadata"""
    def __init__(self,elem):        
        self.service="WCS"
        self.version="1.1.0"
        self.title = elem.find('{http://www.opengis.net/ows}Title').text
        self.abstract = elem.find('{http://www.opengis.net/ows}Abstract').text
        self.keywords = [f.text for f in elem.findall('{http://www.opengis.net/ows}Keywords/{http://www.opengis.net/ows}Keyword')]
        #self.link = elem.find('{http://www.opengis.net/wcs/1.1}Service/{http://www.opengis.net/wcs/1.1}OnlineResource').attrib.get('{http://www.w3.org/1999/xlink}href', '')
               
        #NOTE: do these belong here?
        self.fees=elem.find('{http://www.opengis.net/wcs/1.1/ows}Fees').text
        self.accessConstraints=elem.find('{http://www.opengis.net/wcs/1.1/ows}AccessConstraints').text
       
       
class ServiceProvider(object):
    """ Abstraction for ServiceProvider metadata 
    implements IServiceProviderMetadata """
    def __init__(self,elem):
        self.provider=elem.find('{http://www.opengis.net/ows}ProviderName').text
        self.contact=ServiceContact(elem.find('{http://www.opengis.net/ows}ServiceContact'))
        self.contact='How to contact the service provider (string).'
        self.url="URL for provider's web site (string)."


#TO DECIDE: How to model the contact detials - explicitly or truncated?
class Address(object):
    def __init__(self,elem):
        self.deliveryPoint=elem.find('{http://www.opengis.net/ows}DeliveryPoint').text
        self.city=elem.find('{http://www.opengis.net/ows}City').text
        self.administrativeArea=elem.find('{http://www.opengis.net/ows}AdministrativeArea').text
        self.postalCode=elem.find('{http://www.opengis.net/ows}PostalCode').text
        self.country=elem.find('{http://www.opengis.net/ows}Country').text
        self.electronicMailAddress=elem.find('{http://www.opengis.net/ows}ElectronicMailAddress').text
        self.email=self.electronicMailAddress #shorthand alias
        

class Phone(object):
    def __init__(self,elem):
        self.voice=elem.find('{http://www.opengis.net/ows}Voice').text
        self.facsimile=elem.find('{http://www.opengis.net/ows}Facsimile').text
        self.fax=self.facsimile #shorthand alias

class ContactInfo(object):
    def __init__(self,elem):
        #self.address=elem.find
        self.phone=Phone(elem.find('{http://www.opengis.net/ows}Phone'))
        self.address=Address(elem.find('{http://www.opengis.net/ows}Address'))
        
    
class ServiceContact(object):
    def __init__(self,elem):
        self.individualName=elem.find('{http://www.opengis.net/ows}IndividualName').text
        self.positionName=elem.find('{http://www.opengis.net/ows}PositionName').text
        contact=elem.find('{http://www.opengis.net/ows}ContactInfo')
        if contact is not None:
            self.contactInfo=ContactInfo(contact)
        else:
            self.contactInfo = None
        
  
class ContentMetadata(object):
    """Abstraction for WCS CoverageSummary
    """
    def __init__(self, elem, parent, service):
        """Initialize."""
        #TODO - examine the parent for bounding box info.
        
        self._service=service
        self._elem=elem
        self._parent=parent
        self.id=self._checkChildAndParent('{http://www.opengis.net/wcs/1.1}Identifier')
        self.description =self._checkChildAndParent('{http://www.opengis.net/wcs/1.1}Description')           
        self.title =self._checkChildAndParent('{http://www.opengis.net/ows}Title')
        self.abstract =self._checkChildAndParent('{http://www.opengis.net/ows}Abstract')
        
        #keywords.
        self.keywords=[]
        for kw in elem.findall('{http://www.opengis.net/ows}Keywords/{http://www.opengis.net/ows}Keyword'):
            if kw is not None:
                self.keywords.append(kw.text)
        
        #also inherit any keywords from parent coverage summary (if there is one)
        if parent is not None:
            for kw in parent.findall('{http://www.opengis.net/ows}Keywords/{http://www.opengis.net/ows}Keyword'):
                if kw is not None:
                    self.keywords.append(kw.text)
            
        
        self.boundingBoxWGS84 = None
        b = elem.find('{http://www.opengis.net/ows}WGS84BoundingBox')
        if b is not None:
            lc=b.find('{http://www.opengis.net/ows}LowerCorner').text
            uc=b.find('{http://www.opengis.net/ows}UpperCorner').text
            self.boundingBoxWGS84 = (
                    float(lc.split()[0]),float(lc.split()[1]),
                    float(uc.split()[0]), float(uc.split()[1]),
                    )
                
        # bboxes - other CRS 
        self.boundingBoxes = []
        for bbox in elem.findall('{http://www.opengis.net/ows}BoundingBox'):
            if bbox is not None:
                lc=b.find('{http://www.opengis.net/ows}LowerCorner').text
                uc=b.find('{http://www.opengis.net/ows}UpperCorner').text
                boundingBox =  (
                        float(lc.split()[0]),float(lc.split()[1]),
                        float(uc.split()[0]), float(uc.split()[1]),
                        b.attrib['crs'])
                self.boundingBoxes.append(boundingBox)
        
        #SupportedCRS
        self.supportedCRS=[]
        for crs in elem.findall('{http://www.opengis.net/wcs/1.1}SupportedCRS'):
            self.supportedCRS.append(crs.text)
            
        #SupportedFormats         
        self.supportedFormats=[]
        for format in elem.findall('{http://www.opengis.net/wcs/1.1}SupportedFormat'):
            self.supportedFormats.append(format.text)
            
            
    #time limits/postions require a describeCoverage request therefore only resolve when requested
    def _getTimeLimits(self):
         timelimits=[]
         for elem in self._service.getDescribeCoverage(self.id).findall(ns('CoverageDescription/')+ns('Domain/')+ns('TemporalDomain/')+ns('TimePeriod/')):
             subelems=elem.getchildren()
             timelimits=[subelems[0].text,subelems[1].text]
         return timelimits
    timelimits=property(_getTimeLimits, None)
    
    def _checkChildAndParent(self, path):
        ''' checks child coverage  summary, and if item not found checks higher level coverage summary'''
        try:
            value = self._elem.find(path).text
        except:
            try:
                value = self._parent.find(path).text
            except:
                value = None
        return value  