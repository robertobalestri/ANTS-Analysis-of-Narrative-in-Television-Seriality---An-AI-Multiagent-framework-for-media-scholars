import React, { useState, useEffect } from 'react';
import {
  Box,
  VStack,
  Heading,
  FormControl,
  FormLabel,
  Input,
  Button,
  Text,
  useToast,
  Divider,
  FormHelperText,
  Spinner,
  Alert,
  AlertIcon,
  HStack,
  IconButton,
} from '@chakra-ui/react';
import { ViewIcon, ViewOffIcon } from '@chakra-ui/icons';
import { ApiClient } from '@/services/api/ApiClient';
import { isApiSuccess } from '@/architecture/types/api';

interface EnvVar {
  name: string;
  value: string;
  description: string;
  required: boolean;
}

const api = new ApiClient();

export const SettingsPanel: React.FC = () => {
  const [envVars, setEnvVars] = useState<EnvVar[]>([]);
  const [formData, setFormData] = useState<Record<string, string>>({});
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [showSensitive, setShowSensitive] = useState<Record<string, boolean>>({});
  const toast = useToast();

  useEffect(() => {
    fetchSettings();
  }, []);

  const fetchSettings = async () => {
    setIsLoading(true);
    try {
      const response = await api.request<EnvVar[]>('/settings/env');
      console.log('Settings API Response:', response);
      if (isApiSuccess<EnvVar[]>(response)) {
        setEnvVars(response.data);
        const initialData: Record<string, string> = {};
        response.data.forEach((v) => {
          initialData[v.name] = v.value;
        });
        setFormData(initialData);
      } else {
        toast({
          title: 'Error loading settings',
          description: (response as any).error || 'Could not fetch environment variables',
          status: 'error',
        });
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleInputChange = (name: string, value: string) => {
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const handleSave = async () => {
    setIsSaving(true);
    try {
      const response = await api.request('/settings/env', {
        method: 'POST',
        body: JSON.stringify({ settings: formData }),
      });

      if (isApiSuccess(response)) {
        toast({
          title: 'Settings saved',
          description: 'Environment variables updated. Some changes may require a server restart.',
          status: 'success',
          duration: 5000,
          isClosable: true,
        });
      } else {
        toast({
          title: 'Error saving settings',
          description: (response as any).error || 'Unknown error',
          status: 'error',
        });
      }
    } finally {
      setIsSaving(false);
    }
  };

  const toggleSensitive = (name: string) => {
    setShowSensitive(prev => ({ ...prev, [name]: !prev[name] }));
  };

  const isSensitive = (name: string) => {
    return name.includes('KEY') || name.includes('SECRET') || name.includes('PASSWORD');
  };

  if (isLoading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" p={10}>
        <Spinner size="xl" color="blue.500" />
      </Box>
    );
  }

  return (
    <Box bg="white" p={8} borderRadius="lg" shadow="sm">
      <VStack align="stretch" spacing={6}>
        <Box>
          <Heading size="lg" color="blue.600" mb={2}>Environment Settings</Heading>
          <Text color="gray.600">Manage your LLM credentials and application configuration.</Text>
        </Box>

        <Alert status="info" variant="left-accent" borderRadius="md">
          <AlertIcon />
          These settings are saved to your .env file in the backend directory.
        </Alert>

        <Divider />

        <VStack spacing={8} align="stretch">
          {/* LLM Section */}
          <Box>
            <Heading size="md" mb={4} color="gray.700" borderBottom="1px solid" borderColor="gray.100" pb={2}>
              LLM Configuration
            </Heading>
            <VStack spacing={6} align="stretch">
              {envVars.filter(v => v.name.startsWith('LLM_')).map((v) => (
                <FormControl key={v.name} isRequired={v.required}>
                  <FormLabel fontWeight="bold" color="gray.600" fontSize="sm">{v.name}</FormLabel>
                  <HStack>
                    <Input
                      type={isSensitive(v.name) && !showSensitive[v.name] ? "password" : "text"}
                      value={formData[v.name] || ''}
                      onChange={(e) => handleInputChange(v.name, e.target.value)}
                      placeholder={`Enter ${v.name.toLowerCase()}`}
                    />
                    {isSensitive(v.name) && (
                      <IconButton
                        aria-label={showSensitive[v.name] ? "Hide" : "Show"}
                        icon={showSensitive[v.name] ? <ViewOffIcon /> : <ViewIcon />}
                        onClick={() => toggleSensitive(v.name)}
                        variant="ghost"
                      />
                    )}
                  </HStack>
                  <FormHelperText fontSize="xs">{v.description}</FormHelperText>
                </FormControl>
              ))}
            </VStack>
          </Box>

          {/* Embedding Section */}
          <Box>
            <Heading size="md" mb={4} color="gray.700" borderBottom="1px solid" borderColor="gray.100" pb={2}>
              Embedding Configuration
            </Heading>
            <VStack spacing={6} align="stretch">
              {envVars.filter(v => v.name.startsWith('EMBED_')).map((v) => (
                <FormControl key={v.name} isRequired={v.required}>
                  <FormLabel fontWeight="bold" color="gray.600" fontSize="sm">{v.name}</FormLabel>
                  <HStack>
                    <Input
                      type={isSensitive(v.name) && !showSensitive[v.name] ? "password" : "text"}
                      value={formData[v.name] || ''}
                      onChange={(e) => handleInputChange(v.name, e.target.value)}
                      placeholder={`Enter ${v.name.toLowerCase()}`}
                    />
                    {isSensitive(v.name) && (
                      <IconButton
                        aria-label={showSensitive[v.name] ? "Hide" : "Show"}
                        icon={showSensitive[v.name] ? <ViewOffIcon /> : <ViewIcon />}
                        onClick={() => toggleSensitive(v.name)}
                        variant="ghost"
                      />
                    )}
                  </HStack>
                  <FormHelperText fontSize="xs">{v.description}</FormHelperText>
                </FormControl>
              ))}
            </VStack>
          </Box>
        </VStack>

        <Divider pt={4} />

        <Box display="flex" justifyContent="flex-end">
          <Button
            colorScheme="blue"
            size="lg"
            onClick={handleSave}
            isLoading={isSaving}
            px={10}
          >
            Save Settings
          </Button>
        </Box>
      </VStack>
    </Box>
  );
};
