import sys
import argparse
from agent import get_node_agent, get_file_sender, get_logger

logger = get_logger('main')

def cmd_listen():
    agent = get_node_agent()
    try:
        agent.start()
    except KeyboardInterrupt:
        logger.info("\nInterrupt received in main")
    finally:
        agent.stop()
        logger.info("Goodbye!")

def cmd_send(filename: str, destination: str, algorithm: str = 'astar'):
    logger.info(f"Sending file: {filename} → {destination} ({algorithm})")
    
    sender = get_file_sender()
    success = sender.send_file_to_destination(filename, destination, algorithm)
    
    if success:
        logger.info("File transfer initiated successfully")
        sys.exit(0)
    else:
        logger.error("File transfer failed")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(
        description='SAGSIN File Agent - Hop-by-hop file transfer'
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    parser_listen = subparsers.add_parser('listen', help='Start listening for incoming files')
    
    parser_send = subparsers.add_parser('send', help='Send a file to destination')
    parser_send.add_argument('filename', help='Filename in send-file directory')
    parser_send.add_argument('destination', help='Destination node name')
    parser_send.add_argument('--algo', default='astar', choices=['astar', 'dijkstra', 'greedy'],
                           help='Routing algorithm (default: astar)')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    if args.command == 'listen':
        cmd_listen()
    elif args.command == 'send':
        cmd_send(args.filename, args.destination, args.algo)
    else:
        parser.print_help()
        sys.exit(1)

if __name__ == '__main__':
    main()
