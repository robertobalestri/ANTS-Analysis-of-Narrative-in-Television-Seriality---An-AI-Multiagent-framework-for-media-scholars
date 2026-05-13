import React from 'react';
import {
  Box,
  Heading,
  HStack,
  IconButton,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalCloseButton,
  Text,
  VStack,
} from '@chakra-ui/react';
import { DownloadIcon } from '@chakra-ui/icons';

interface EpisodeVideoPlayerProps {
  isOpen: boolean;
  onClose: () => void;
  videoUrl: string;
  episodeTitle: string;
}

export const EpisodeVideoPlayer: React.FC<EpisodeVideoPlayerProps> = ({
  isOpen,
  onClose,
  videoUrl,
  episodeTitle,
}) => {
  return (
    <Modal isOpen={isOpen} onClose={onClose} size="5xl" isCentered>
      <ModalOverlay bg="blackAlpha.800" backdropFilter="blur(10px)" />
      <ModalContent bg="gray.900" color="white" borderRadius="xl">
        <ModalHeader borderBottomWidth="1px" borderColor="gray.700">
          <HStack justify="space-between" pr={8}>
            <VStack align="start" spacing={0}>
              <Text fontSize="xs" color="blue.400" fontWeight="bold" textTransform="uppercase">
                Now Playing
              </Text>
              <Heading size="md">{episodeTitle}</Heading>
            </VStack>
            <IconButton
              as="a"
              href={videoUrl}
              download
              aria-label="Download video"
              icon={<DownloadIcon />}
              size="sm"
              variant="ghost"
              colorScheme="whiteAlpha"
            />
          </HStack>
        </ModalHeader>
        <ModalCloseButton />
        <ModalBody p={0} bg="black">
          <Box position="relative" width="100%" paddingTop="56.25%">
            <Box
              as="video"
              position="absolute"
              top={0}
              left={0}
              width="100%"
              height="100%"
              controls
              autoPlay
              src={videoUrl}
              style={{
                outline: 'none',
              }}
            >
              Your browser does not support the video tag.
            </Box>
          </Box>
        </ModalBody>
      </ModalContent>
    </Modal>
  );
};
